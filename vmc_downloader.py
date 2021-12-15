#!/bin/python

import glob
import hashlib
import os
import re
import sys
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
        sys.stdout.write("-" + filename + "\r")
        href = a["href"]

        resp = ses.get(href)

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
            print("\r--exists {}".format(filename))
        else:
            print("")
            with open(filename, "wb") as f:
                f.write(resp.content)


if len(sys.argv) != 3:
    print("usage:", sys.argv[0], "<target_path>", "<vmc_url>")
    exit(1)


ses = requests.Session()
login_url = "https://vmc.medunigraz.at/moodle/login/index.php"

username, password = ratools.get_credentials(login_url)



os.chdir(sys.argv[1])
hashes = []
for name in glob.glob('**', recursive=True):
    if os.path.isfile(name):
        hash = hashlib.sha512(open(name, 'rb').read()).hexdigest()
        hashes.append(hash)


print("Login...")
resp = ses.get(login_url)
soup = BeautifulSoup(resp.content, "html.parser")
token = soup.find_all("input", {"type": "hidden", "name": "logintoken"})[
    0]["value"]
resp = ses.post(login_url, data={
                "username": username, "password": password, "logintoken": token, "anchor": ""})

download_url = "https://vmc.medunigraz.at/moodle/course/index.php?categoryid=" + \
    sys.argv[2]
# download_url = "https://vmc.medunigraz.at/moodle/course/view.php?id=" + \
#    sys.argv[2]
resp = ses.get(download_url)
soup = BeautifulSoup(resp.content, "html.parser")

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
            if "name" in i.attrs:
                data[i["name"]] = i["value"]
        ses.post("https://vmc.medunigraz.at/moodle/enrol/index.php", data=data)
    download_course(download_url)
    os.chdir("..")

exit(0)
