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
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

load_dotenv()

# Setup Logger
logging.basicConfig(filename="log.txt",
                    format="%(asctime)s %(message)s", filemode="a")
logger = logging.getLogger()
logger.setLevel(level=logging.INFO)

RECOVERED_BACKUP = {"1/22/20": 0, "1/23/20": 0, "1/24/20": 0, "1/25/20": 0, "1/26/20": 0, "1/27/20": 0, "1/28/20": 0, "1/29/20": 0, "1/30/20": 0, "1/31/20": 0, "2/1/20": 0, "2/2/20": 0, "2/3/20": 0, "2/4/20": 0, "2/5/20": 0, "2/6/20": 0, "2/7/20": 0, "2/8/20": 0, "2/9/20": 0, "2/10/20": 0, "2/11/20": 0, "2/12/20": 0, "2/13/20": 0, "2/14/20": 0, "2/15/20": 0, "2/16/20": 3, "2/17/20": 3, "2/18/20": 3, "2/19/20": 3, "2/20/20": 3, "2/21/20": 3,
                    "2/22/20": 3, "2/23/20": 3, "2/24/20": 3, "2/25/20": 3, "2/26/20": 3, "2/27/20": 3, "2/28/20": 3, "2/29/20": 3, "3/1/20": 3, "3/2/20": 3, "3/3/20": 3, "3/4/20": 3, "3/5/20": 3, "3/6/20": 3, "3/7/20": 3, "3/8/20": 3, "3/9/20": 3, "3/10/20": 4, "3/11/20": 4, "3/12/20": 4, "3/13/20": 4, "3/14/20": 4, "3/15/20": 13, "3/16/20": 13, "3/17/20": 14, "3/18/20": 14, "3/19/20": 15, "3/20/20": 20, "3/21/20": 23, "3/22/20": 27, "3/23/20": 27, "3/24/20": 40}

# Constants
URL = "https://www.mohfw.gov.in/"
DATAFOLDER = os.path.join(os.curdir, "data")
TEMPFOLDER = os.path.join(os.curdir, "temp")
CSV_HEADERS = [
    "state/ut", "confirmed", "cured/discharged", "death"]
REPO_NAME = "ncov-19-india"
REPORT_REPO_NAME = "incov-report"


# Functions
if not os.path.isdir(DATAFOLDER):
    os.mkdir(DATAFOLDER)


def get_scrapped_data(U: str = None):
    try:
        if U is None:
            U = URL
        page = requests.get(U).text
        soup = bs(page, "html.parser")
        return soup.find("section", {"id": "state-data"}).find_all('tbody')[0].find_all("tr")[:-5]
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
        if soup is None:
            soup = get_scrapped_data(URL)

        for tr in soup:
            tds = tr.find_all('td')
            print(f"State/UT: {tds[1].text}, Confirmed (Indian National): {tds[2].text}, Confirmed (Foreign National): {tds[3].text}, Cured/Discharged: {tds[4].text}, Death: {tds[5].text}")
        return True
    except Exception as e:
        print(e)
        logger.error(f"Got Error While Printing Table : {str(e)}")


def state_trend():
    try:
        STATE_DAILY_DATA = {
            "CONFIRMED": "http://api.covid19india.org/states_daily_csv/confirmed.csv",
            "DEATHS": "https://api.covid19india.org/states_daily_csv/deceased.csv",
            "RECOVERED": "https://api.covid19india.org/states_daily_csv/recovered.csv"
        }
        TREND_TABLE = {}
        for key in STATE_DAILY_DATA.keys():
            link = STATE_DAILY_DATA[key]
            df = pd.read_csv(link)
            df = df.fillna(0)
            df = df.astype(int, errors='ignore')
            df = df.iloc[:, :-1]
            TREND_TABLE[key] = df.to_dict("list")
        # print(TREND_TABLE)
        with open(os.path.join(DATAFOLDER, "trend.json"), "w") as f:
            f.write(str(TREND_TABLE).replace("'", '"'))
        print("STATE TREND SUCCESS")
        return True
    except Exception as e:
        return False
        print("STATE TREND FAILED")


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
            for tr in soup:
                tds = tr.find_all("td")
                writer.writerow([tds[1].text, tds[2].text,
                                 tds[3].text, tds[4].text])
        return True
    except Exception as e:
        print(e)
        logger.error("Got Error While Writing CSV : {}".format(str(e)))
        return False


def build_demographic_report():
    try:
        DATA_JSON = "https://api.covid19india.org/raw_data.json"
        res = requests.get(DATA_JSON).json()
        # print(res)
        GENDER_DICT = {"FEMALE": 0, "MALE": 0}
        AGE_DICT = {"0-10": 0, "11-20": 0, "21-30": 0, "31-40": 0, "41-50": 0,
                    "51-60": 0, "61-70": 0, "71-80": 0, "81-90": 0, "91-100": 0}
        NATIONALITY_DICT = dict()
        CURRENT_STATUS_DICT = dict()
        STATE_DICT = dict()
        TYPE_OF_TRANSMISSION = dict()
        for p in res["raw_data"]:
            # print(p)
            if p["gender"] == "M":
                GENDER_DICT["MALE"] += 1
            elif p["gender"] == "F":
                GENDER_DICT["FEMALE"] += 1
            if p["nationality"]:
                N = p["nationality"].lower()
                if N not in NATIONALITY_DICT.keys():
                    NATIONALITY_DICT[N] = 0
                NATIONALITY_DICT[N] += 1
            if p["currentstatus"]:
                S = p["currentstatus"].lower()
                if S not in CURRENT_STATUS_DICT.keys():
                    CURRENT_STATUS_DICT[S] = 0
                CURRENT_STATUS_DICT[S] += 1

            if p["statecode"]:
                S = p["statecode"]
                if S not in STATE_DICT.keys():
                    STATE_DICT[S] = 0
                STATE_DICT[S] += 1

            if p["typeoftransmission"]:
                t = p["typeoftransmission"].lower()
                if t not in TYPE_OF_TRANSMISSION.keys():
                    TYPE_OF_TRANSMISSION[t] = 0
                TYPE_OF_TRANSMISSION[t] += 1

            if p["agebracket"]:
                try:
                    age = int(p["agebracket"])
                except:
                    # print("------")
                    try:
                        #print(p["agebracket"])
                        x = p["agebracket"].split("-")
                        age = int((int(x[0]) + int(x[1]))/2)
                    except:
                        x = p["agebracket"].split(".")
                        age = int(x[0])
                        #print(age)
                #print(age)
                if age >= 0 and age <= 10:
                    AGE_DICT["0-10"] += 1
                elif age > 10 and age <= 20:
                    AGE_DICT["11-20"] += 1
                elif age > 20 and age <= 30:
                    AGE_DICT["21-30"] += 1
                elif age > 30 and age <= 40:
                    AGE_DICT["31-40"] += 1
                elif age > 40 and age <= 50:
                    AGE_DICT["41-50"] += 1
                elif age > 50 and age <= 60:
                    AGE_DICT["51-60"] += 1
                elif age > 60 and age <= 70:
                    AGE_DICT["61-70"] += 1
                elif age > 70 and age <= 80:
                    AGE_DICT["71-80"] += 1
                elif age > 80 and age <= 90:
                    AGE_DICT["81-90"] += 1
                elif age > 90 and age <= 100:
                    AGE_DICT["91-100"] += 1

        # print(TYPE_OF_TRANSMISSION)
        TABLE = {"GENDER": GENDER_DICT, "AGE": AGE_DICT, "NATIONALITY": NATIONALITY_DICT,
                "CSTATUS": CURRENT_STATUS_DICT, "STATE": STATE_DICT, "TRANSMISSION": TYPE_OF_TRANSMISSION}

        with open(os.path.join(DATAFOLDER, "demographic.json"), "w") as f:
            f.write(json.dumps(TABLE))
        print("DEMOGRAPHIC SUCCESS")
        return True
    except Exception as e:
        print(e)
        print("FAILED WRITING DEMOGRAPHIC JSON")
        return False


def push_to_github():
    try:
        file_list = glob.glob(os.path.join(DATAFOLDER, "*.csv"))
        item_list = [x[-14:] for x in file_list]

        file_list.extend([os.path.join(DATAFOLDER, "report.json"),
                          os.path.join(DATAFOLDER, "trend.json"),
                          os.path.join(DATAFOLDER, "demographic.json")])
        item_list.extend(["report.json", "trend.json" , "demographic.json"])
        TOKEN = os.getenv("GHTOKEN")
        g = Github(TOKEN)
        nrepo = g.get_user().get_repo(REPO_NAME)
        commit_msg = ":bug: {}".format(datetime.now(
            pytz.timezone("Asia/Kolkata")).isoformat())
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


def build_json(soup=None):
    try:
        if soup is None:
            soup = get_scrapped_data()
        total_c = total_e = total_d = total_s = 0
        table = []
        for tr in soup:
            tds = tr.find_all("td")
            total_e += int(tds[2].text)
            total_c += int(tds[3].text)
            total_d += int(str(tds[4].text).replace("#", ""))
            total_s += 1
            table.append({"state": tds[1].text, "effected": int(
                tds[2].text), "recovered": int(tds[3].text), "death": int(str(tds[4].text).replace("#", ""))})
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


def send_email(status: bool, msg="SUCCESS"):
    port = 587  # For starttls
    smtp_server = "smtp.gmail.com"
    sender_email = os.getenv("FROM_EMAIL")
    receiver_email = os.getenv("FROM_EMAIL")
    password = os.getenv("EMAIL_PASS")
    message = f"""
    INCOV PROJECT RUN REPORT
    ------------------------

    LAST RUN : {datetime.now(pytz.timezone("Asia/Kolkata")).isoformat()}

    LAST STATUS : {"SUCCESS!" if status else "FAILED!"}

    LAST RUN MESSAGE : {"ALL fUNCTIONS RAN SUCCESSFULLY" if status else "FAILED ON : " + msg}
    """

    fromaddr = sender_email
    toaddr = receiver_email
    msg = MIMEMultipart()
    msg['From'] = fromaddr
    msg['To'] = toaddr
    msg['Subject'] = f"Incov Project : Status : {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d-%m_%H-%M')}"
    body = message
    msg.attach(MIMEText(body, 'plain'))
    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    s.login(fromaddr, password)
    text = msg.as_string()
    s.sendmail(fromaddr, toaddr, text)
    s.quit()
    print("SENT EMAIL")


def main():
    soup = get_scrapped_data(URL)
    if fetch_data_from_github():
        print("DATA FOLDER FETCH COMPLETED")
        c = write_csv(soup)
        if c:
            logger.info("CSV WRITE COMPLETED")
            print("CSV WRITE COMPLETED")

            rep = build_json(soup)
            tr = state_trend() # build_daily_data_json()
            d = build_demographic_report() 
            gh = push_to_github()

            if gh and rep and tr and d:
                logger.info("ALL GITHUB PUSH COMPLETED")

                print("ALL GITHUB PUSH COMPLETED")
                #send_email(True)
            else:
                if not gh:
                    logger.error("DATA PUSH FAILED")
                    print("DATA PUSH FAILED")
                    send_email(False, "DATA")
                if not rep:
                    logger.error("REPORT PUSH FAILED")
                    print("REPORT PUSH FAILED")
                    send_email(False, "REPORT")

                if not d:
                    logger.error("DEMOGRAPHIC BUILD FAILED")
                    print("DEMOGRAPHIC BUILD FAILED")
                    send_email(False , "DEMOGRAPHIC")

        else:
            logger.error("CSV WRITE FAILED")
            print("CSV WRITE FAILED")
            send_email(False, "CSV")

    else:
        print("DATA FOLDER FETCH FAILED")
        send_email(False, "FOLDER")


if __name__ == "__main__":
    main()
    #print(build_demographic_report())
    #print(state_trend())
