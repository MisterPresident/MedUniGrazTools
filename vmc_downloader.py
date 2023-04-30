#!/bin/python

import glob
import hashlib
import os
import re
import sys
import time
from pathlib import Path

from ratools import ratools
import requests
from bs4 import BeautifulSoup


def download_course(download_url):
    resp = ses.get(download_url)
    soup = BeautifulSoup(resp.content, "html.parser")
    res = soup.find_all("li", {"class": "modtype_resource"})

    for r in res:
        a = r.find("a")
        filename = a.find(text=True)
        sys.stdout.write(" - " + filename + "\r")
        href = a["href"]

        for i in range(1):
            try:
                resp = ses.get(href)
                break
            except requests.exceptions.ConnectionError:
                time.sleep(1)
                print("Connection Error, sleeping...")

        arg = "Content-Disposition"
        if not arg in resp.headers:
            soup = BeautifulSoup(resp.content, "html.parser")
            href = soup.find("div", {"class": "resourceworkaround"})
            if href is None:
                continue
            href = href.find("a")
            if href is None:
                continue
            href = href["href"]
            resp = ses.get(href)
        filename += "." + re.findall('filename=(.+)',
                                     resp.headers[arg])[0][1:-1].split(".")[-1]
        filename = filename.strip()
        filename = filename.replace(" ", "_")
        filename = filename.replace("/", "_")

        hash = hashlib.sha512(resp.content).hexdigest()
        if hash in hashes:
            print("\r -- exists {}".format(filename))
        else:
            print("")
            with open(filename, "wb") as f:
                f.write(resp.content)


if len(sys.argv) != 3:
    print("usage:", sys.argv[0], "<target_path>", "<vmc_url>")
    exit(1)

ses = requests.Session()
login_url = "https://vmc.medunigraz.at/moodle"

username, password = ratools.get_credentials(login_url)

if not os.path.exists(sys.argv[1]):
    os.mkdir(sys.argv[1])

os.chdir(sys.argv[1])

hashes = []
for name in glob.glob('**', recursive=True):
    if os.path.isfile(name):
        hash = hashlib.sha512(open(name, 'rb').read()).hexdigest()
        hashes.append(hash)

print("Login...")
resp = ses.get(login_url)


soup = BeautifulSoup(resp.content, "html.parser")

if "onload" in soup.select_one("body").attrs:
    action_url = soup.select_one("body")["onload"].split("'")[1]
    resp = ses.get(action_url)

soup = BeautifulSoup(resp.content, "html.parser")
action_url = soup.select_one("form")["action"]

data = {
    "j_username": username,
    "j_password": password,
    "_eventId_proceed": ""
}

post_url = "https://idp.medunigraz.at" + action_url
resp = ses.post(post_url,
                headers={
                    "referer": post_url,
                    'Content-Type': 'application/x-www-form-urlencoded'}, data=data)

with open("/tmp/test.html", "wb") as f:
    f.write(resp.content)

inital_url = resp.url
#soup = BeautifulSoup(resp.content, "html.parser")
#action_url = soup.select_one("form")["action"]
#data = soup.select("input")
#data={d["name"]: d["value"] for d in data if "name" in d.attrs}
#resp = ses.post(action_url, data=data, headers={"referer": "https://idp.medunigraz.at/", 'Content-Type': 'application/x-www-form-urlencoded'})

soup = BeautifulSoup(resp.content, "html.parser")
title = soup.find("title").text

if title != "Virtueller Medizinischer Campus":
    iframe = soup.find("iframe")
    # send_push
    data_host = "https://" + iframe["data-host"]
    data_sig_request = iframe["data-sig-request"]
    tx_code, app_code = data_sig_request.split(":")
    resp = ses.get(data_host + "/frame/web/v1/auth",
                   params={"tx": tx_code,
                           "parent": resp.url,
                           "v": 2.6
                           }, headers={
            "referer": "https://idp.medunigraz.at/",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"
        })

    resp = ses.post(data_host + "/frame/web/v1/auth",
                    params={"tx": tx_code,
                            "parent": resp.url,
                            "v": 2.6
                            }, headers={
            "referer": "https://idp.medunigraz.at/",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"
        }, data={})

    soup = BeautifulSoup(resp.content, "html.parser")
    data = {x["name"]: x["value"] for x in soup.find_all("input", {"type": "hidden"})}
    resp = ses.get(data_host + "/frame/prompt",
                   params={
                       "sid": data["sid"]
                   },
                   headers={
                       "referer": resp.url
                   })

    print("Sending Push-Notification")
    resp = ses.post(data_host + "/frame/prompt",
                    data={
                        "sid": data["sid"],
                        "device": "phone1",
                        "factor": "Duo Push",
                        "out_of_date": "",
                        "days_out_of_date": "",
                        "days_to_block": None
                    },
                    headers={
                        "referer": resp.url
                    })

    tf_auth = resp.json()

    while True:
        resp = ses.post(data_host + "/frame/status",
                        data={
                            "sid": data["sid"],
                            "txid": tf_auth["response"]["txid"]
                        },
                        headers={
                            "referer": resp.url
                        })
        j_resp = resp.json()
        if "status_code" in j_resp["response"] and j_resp["response"]["status_code"] == "allow":
            print("Accepted")
            resp = ses.post(data_host + j_resp["response"]["result_url"], data = {
                "sid": data["sid"]
            })
            auth_code = resp.json()["response"]["cookie"]
            sig_response = auth_code + ":" + app_code
            resp = ses.post(inital_url, headers={"referer": inital_url}, data = {
                '_eventId': 'proceed',
                'sig_response': sig_response,
            })
            soup = BeautifulSoup(resp.content, "html.parser")
            resp = ses.post(soup.find("form")["action"], data={
                x["name"]: x["value"] for x in soup.find_all("input", {"type": "hidden"})
            })

            with open("/tmp/test.html", "wb") as f:
                f.write(resp.content)
            break
        time.sleep(1)

download_url = "https://vmc.medunigraz.at/moodle/course/index.php?categoryid=" + \
               sys.argv[2]

resp = ses.get(download_url)
soup = BeautifulSoup(resp.content, "html.parser")

with open("/tmp/test.html", "wb") as f:
    f.write(resp.content)

res = soup.find_all("div", {"class": "coursebox"})

for course in res:
    course_txt = course.text.strip()
    print(course_txt)
    Path(course_txt).mkdir(exist_ok=True)
    os.chdir(course_txt)
    download_url = course.find("a")["href"]
    resp = ses.get(download_url)
    soup = BeautifulSoup(resp.content, "html.parser")
    btn_einschreiben = soup.find("input", {"value": "Einschreiben"})
    if btn_einschreiben is not None:
        data = {}
        for i in soup.find_all("input"):
            if "name" in i.attrs and "value" in i.attrs:
                data[i["name"]] = i["value"]
        ses.post("https://vmc.medunigraz.at/moodle/enrol/index.php", data=data)
    download_course(download_url)
    os.chdir("..")

exit(0)
