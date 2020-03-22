import requests
import csv
import json
from bs4 import BeautifulSoup as bs
from datetime import datetime, date
import pytz
import os
import logging
from flask import Flask, jsonify
from dotenv import load_dotenv
from github import Github, InputGitTreeElement
import glob
from string import Template
import pandas as pd

load_dotenv()

# Setup Logger
logging.basicConfig(filename="log.txt",
                    format="%(asctime)s %(message)s", filemode="a")
logger = logging.getLogger()
logger.setLevel(level=logging.INFO)

# Constants
URL = "https://www.mohfw.gov.in/"
DATAFOLDER = os.path.join(os.curdir, "data")
TEMPFOLDER = os.path.join(os.curdir, "temp")
CSV_HEADERS = [
    "state/ut", "confirmed (indian)", "confirmed (foreign)", "cured/discharged", "death"]
REPO_NAME = "ncov-19-india"
REPORT_REPO_NAME = "incov-report"

DAILY = {
    "CONFIRMED": "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Confirmed.csv",
    "DEATHS": "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Deaths.csv",
    "RECOVERED": "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Recovered.csv"
}
# Functions


if not os.path.isdir(DATAFOLDER):
    os.mkdir(DATAFOLDER)


def build_daily_data_json():
    if not os.path.isdir(TEMPFOLDER):
        os.mkdir(TEMPFOLDER)

    try:
        TABLE = dict.fromkeys(["CONFIRMED", "DEATHS", "RECOVERED"])
        for k in DAILY.keys():
            p = pd.read_csv(DAILY[k]).drop(["Province/State" , "Lat" , "Long"] , axis=1)
            newframe = p.loc[p["Country/Region"] == "India"]
            newframe = newframe.drop(["Country/Region"], axis=1)
            #print(newframe.sum())
            x = {}
            for i in newframe:
                x[i] = int(newframe[i].values[0])
            TABLE[k] = x
        json.dump(TABLE, open(os.path.join(DATAFOLDER, "trend.json"), "w"))
        return True

    except Exception as e:
        print(e)
        return False


def get_scrapped_data(URL: str):
    try:
        page = requests.get(URL).text
        return bs(page, "html.parser")
    except Exception as e:
        print(e)
        logger.error(f"Got Error While Fetching Source : {str(e)}")
        return False


def fetch_data_from_github():
    try:
        req = requests.get("https://api.github.com/repos/{}/{}/contents/{}".format(
            "bauripalash", REPO_NAME, "data")).json()
        # print(req)
        for item in req:
            content = requests.get(
                item["download_url"], allow_redirects=True).content.decode("utf-8")
            with open(os.path.join(DATAFOLDER, item["name"]), "w") as f:
                f.write(content)
        return True
    except Exception as e:
        print(e)
        logger.error("Cannot Fetch Data Folder From Github")
        return False


def print_data_table(soup=None):
    try:
        if not soup is None:
            soup = get_scrapped_data(URL)

        for tr in soup.find_all('tbody')[1].find_all('tr')[:-1]:
            tds = tr.find_all('td')
            print(f"State/UT: {tds[1].text}, Confirmed (Indian National): {tds[2].text}, Confirmed (Foreign National): {tds[3].text}, Cured/Discharged: {tds[4].text}, Death: {tds[5].text}")
        return True
    except Exception as e:
        print(e)
        logger.error(f"Got Error While Printing Table : {str(e)}")

def print_data(soup):
    print(soup.find_all('tbody')[1].find_all("tr")[:-1])


def write_csv(soup=None):
    try:
        if soup is None:
            soup = get_scrapped_data(URL)

        filename = str(date.today().isoformat()) + ".csv"

        if not os.path.isfile(DATAFOLDER):
            open(os.path.join(DATAFOLDER, filename), "w").close()

        with open(os.path.join(DATAFOLDER, filename), "w") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
            #soup = get_scrapped_data(URL)
            for tr in soup.find_all('tbody')[1].find_all("tr")[:-1]:
                tds = tr.find_all("td")
                writer.writerow([tds[1].text, tds[2].text,
                                 tds[3].text, tds[4].text, tds[5].text])
        return True
    except Exception as e:
        print(e)
        logger.error("Got Error While Writing CSV : {}".format(str(e)))
        return False


def push_to_github():
    try:
        file_list = glob.glob(os.path.join(DATAFOLDER, "*.csv"))
        item_list = [x[-14:] for x in file_list]

        file_list.extend([os.path.join(DATAFOLDER, "report.json"),
                          os.path.join(DATAFOLDER, "trend.json")])
        item_list.extend(["report.json", "trend.json"])
        TOKEN = os.getenv("GHTOKEN")
        g = Github(TOKEN)
        nrepo = g.get_user().get_repo(REPO_NAME)
        commit_msg = "AUTO UPDATE :bug:"
        master_ref = nrepo.get_git_ref("heads/master")
        master_sha = master_ref.object.sha
        base_tree = nrepo.get_git_tree(master_sha)
        elist = []
        for i, entry in enumerate(file_list):
            with open(entry) as input_file:
                data = input_file.read()
            elem = InputGitTreeElement(
                "data/" + item_list[i], '100644', 'blob', data)
            elist.append(elem)
        tree = nrepo.create_git_tree(elist)
        parent = nrepo.get_git_commit(master_sha)
        commit = nrepo.create_git_commit(commit_msg, tree, [parent])
        master_ref.edit(commit.sha)
        # print(elist)
        return True
    except Exception as e:
        print(e)
        logger.error(e)
        return False


def build_json(soup):
    try:
        total_c = total_e = total_d = total_s = 0
        table = []
        for tr in soup.find_all('tbody')[1].find_all("tr")[:-1]:
            tds = tr.find_all("td")
            total_e += int(tds[2].text) + int(tds[3].text)
            total_c += int(tds[4].text)
            total_d += int(tds[5].text)
            total_s += 1
            table.append({"state": tds[1].text, "effected": int(
                tds[2].text) + int(tds[3].text), "recovered": int(tds[4].text), "death": int(tds[5].text)})
        table.append({"total_effected": total_e, "total_cured": total_c, "total_death": total_d, "total_states": total_s,
                      "last_update": datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%H:%M:%S - %d-%m-%Y")})
        # print(table)
        #rj = json.dumps(table)
        json.dump(table, open(os.path.join(DATAFOLDER, "report.json"), "w"))
        # print(rj)
        return True
    except Exception as e:
        print(e)
        logger.error("Failed to Build REPORT JSON")
        return False


def main():
    soup = get_scrapped_data(URL)
    if fetch_data_from_github():
        print("DATA FOLDER FETCH COMPLETED")
        c = write_csv(soup)
        if c:
            logger.info("CSV WRITE COMPLETED")
            print("CSV WRITE COMPLETED")

            rep = build_json(soup)
            tr = build_daily_data_json()
            gh = push_to_github()

            if gh and rep and tr:
                logger.info("ALL GITHUB PUSH COMPLETED")

                print("ALL GITHUB PUSH COMPLETED")
            else:
                if not gh:
                    logger.error("DATA PUSH FAILED")
                    print("DATA PUSH FAILED")
                if not rep:
                    logger.error("REPORT PUSH FAILED")
                    print("REPORT PUSH FAILED")
        else:
            logger.error("CSV WRITE FAILED")
            print("CSV WRITE FAILED")

    else:
        print("DATA FOLDER FETCH FAILED")


if __name__ == "__main__":
    main()
    #print_data(get_scrapped_data(URL))
    # push_to_github()
    # fetch_data_from_github()
    #soup = get_scrapped_data(URL)
    # build_json(soup)
    # push_to_github()
    # build_report(soup)
    #c = write_csv(soup)
    # if c:
    #    logger.info("COMPLETED!")
    #   print("CSV COMPLETE")
    # else:
    #    logger.critical("FAILED!")
    #    print('CSV FAIL')
    #p = push_to_github()
    # if p:
    #    logger.info("PUSH DONE!")
    #    print("GIT COMPLETE")
    # else:
    #    logger.critical("PUSH FAILED!")
    #    print("GIT FAIL")
