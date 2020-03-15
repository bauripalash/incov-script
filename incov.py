import requests
import csv
from bs4 import BeautifulSoup as bs
from datetime import date
import os
import logging
from flask import Flask, jsonify
from dotenv import load_dotenv
from github import Github, InputGitTreeElement
import glob
from string import Template


load_dotenv()

# Setup Logger
logging.basicConfig(filename="log.txt",
                    format="%(asctime)s %(message)s", filemode="a")
logger = logging.getLogger()
logger.setLevel(level=logging.INFO)

# Constants
URL = "https://www.mohfw.gov.in/"
DATAFOLDER = os.path.join(os.curdir, "data")
CSV_HEADERS = [
    "state/ut", "confirmed (indian)", "confirmed (foreign)", "cured/discharged", "death"]
REPO_NAME = "ncov-19-india"
REPORT_REPO_NAME = "incov-report"
# Functions


def get_scrapped_data(URL : str):
    try:
        page = requests.get(URL).text
        return bs(page, "html.parser")
    except Exception as e:
        print(e)
        logger.error(f"Got Error While Fetching Source : {str(e)}")
        return False


def print_data(soup=None ):
    try:
        if not soup is None:
            soup = get_scrapped_data(URL)

        for tr in soup.find_all('tr')[1:-1]:
            tds = tr.find_all('td')
            print(f"State/UT: {tds[1].text}, Confirmed (Indian National): {tds[2].text}, Confirmed (Foreign National): {tds[3].text}, Cured/Discharged: {tds[4].text}, Death: {tds[5].text}")
        return True
    except Exception as e:
        print(e)
        logger.error(f"Got Error While Printing Table : {str(e)}")


def write_csv(soup = None ):
    try:
        if soup is None:
            soup = get_scrapped_data(URL)
            
        filename = str(date.today().isoformat()) + ".csv"

        if not os.path.isdir(DATAFOLDER):
            os.mkdir(DATAFOLDER)

        if not os.path.isfile(DATAFOLDER):
            open(os.path.join(DATAFOLDER, filename), "w").close()

        with open(os.path.join(DATAFOLDER, filename), "w") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
            #soup = get_scrapped_data(URL)
            for tr in soup.find_all("tr")[1:-1]:
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
                "data/" + entry[-14:], '100644', 'blob', data)
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

def push_report_to_github():
    try:
        file_list = [
                os.path.join(os.curdir , "REPORT-index.html"),
                os.path.join(os.curdir , "REPORT-CNAME")
                ]
        remote_files = ["index.html" , "CNAME"]
        TOKEN = os.getenv("GHTOKEN")
        g = Github(TOKEN)
        nrepo = g.get_user().get_repo(REPORT_REPO_NAME)
        commit_msg = "REPORT AUTO UPDATE :bug:"
        master_ref = nrepo.get_git_ref("heads/master")
        master_sha = master_ref.object.sha
        base_tree = nrepo.get_git_tree(master_sha)
        elist = []
        for i, entry in enumerate(file_list):
            with open(entry) as input_file:
                data = input_file.read()
            elem = InputGitTreeElement(remote_files[i], '100644', 'blob', data)
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

def parse_html(effected : int , cured : int , death : int , states : int , table : int):
    TEMPLATEFILE = "template.html"
    TABLE_ROW_TEMPLATE = "<tr><td>$S</td><td>$E</td><td>$C</td><td>$D</td></tr>"
    TEMP_ROW = ""
    for t in table:
        context = {
                "S" : t[0],
                "E" : int(t[1])+int(t[2]),
                "C" : t[3],
                "D" : t[4]
                }
        TEMP_ROW += Template(TABLE_ROW_TEMPLATE).safe_substitute(**context)
    context = {
            "EFFECTED" : effected,
            "DEATHS" : death,
            "RECOVERED" : cured,
            "STATES" : states,
            "TABLE" : TEMP_ROW
            }
    return Template(open(TEMPLATEFILE).read()).safe_substitute(**context)



def build_report(soup=None):
    try:
        total_effected = 0
        total_death = 0
        total_states = 0
        total_cured = 0
        table = []

        if soup is None:
            soup = get_scrapped_data(URL)

        for tr in soup.find_all("tr")[1:-1]:
            tds = tr.find_all("td")

            total_effected += int(tds[2].text) + int(tds[3].text)
            total_cured += int(tds[4].text)
            total_death += int(tds[5].text)
            total_states += 1
            
            table.append([tds[1].text, tds[2].text,
                                 tds[3].text, tds[4].text, tds[5].text])
        
        #print(total_effected , table)
        phtml = parse_html(total_effected , total_cured , total_death , total_states , table)
        with open("REPORT-index.html" , "w") as f:
            f.write(phtml)
        return True

    except Exception as e:
        print(e)
        return False


def main():
    soup = get_scrapped_data(URL)
    c = write_csv(soup)
    if c:
        logger.info("CSV WRITE COMPLETE")
        print("CSV WRITE COMPLETE")
        gh = push_to_github()
        if build_report(soup):
            rep = push_report_to_github()
        else:
            logger.error("REPORT BUILD FAILED")
            print("REPORT BUILD FAILED")
        
        if gh and rep:
            logger.info("ALL GITHUB PUSH COMPLETE")
            print("ALL GITHUB PUSH COMPLETE")
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


if __name__ == "__main__":
    main()
    #soup = get_scrapped_data(URL)
    #build_report(soup)
    #c = write_csv(soup)
    #if c:
    #    logger.info("COMPLETED!")
    #   print("CSV COMPLETE")
    #else:
    #    logger.critical("FAILED!")
    #    print('CSV FAIL')
    #p = push_to_github()
    #if p:
    #    logger.info("PUSH DONE!")
    #    print("GIT COMPLETE")
    #else:
    #    logger.critical("PUSH FAILED!")
    #    print("GIT FAIL")
