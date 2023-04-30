import datetime
import urllib.parse
import xml.etree.ElementTree as ET
from furl import furl

from bs4 import BeautifulSoup
from ratools import ratools


def printer(s, always=False):
    verbose = False
    if always:
        print(s)
    elif verbose:
        print(s)


s = ratools.get_requests_session()

print("Login...")
user, password = ratools.get_credentials("https://medunigraz.at")

s.get("https://online.medunigraz.at/")

r = s.post("https://online.medunigraz.at/mug_online/ee/rest/auth/user", headers={"accept": "application/json"}).json()
url = r['resource'][0]['content']['authenticationResponse']['authEndpointUrl']
statewrapper = urllib.parse.parse_qs(url)["pStateWrapper"][0]

data = {
    "pConfirm": "X",
    "pPassword": password,
    "pStateWrapper": statewrapper,
    "pUsername": user
}
r = s.post("https://online.medunigraz.at/mug_online/pl/ui/$ctx/wbOAuth2.approve", data=data)
if r.status_code != 200:
    print(r.json()["error_description"])
    exit(1)
print("Login erfolgreich.")

base_url = "https://online.medunigraz.at/mug_online/pl/ui/$ctx;design=ca2;header=max;lang=de/"
r = s.get(base_url + "/wbLVPersonal.wbShowPersonalLV")
print(r.url)
#soup = BeautifulSoup(r.content, "html.parser")

#next_page = soup.select_one("a.coTableNaviNextPage")

#main_url = ""
#if next_page is not None:
#    main_url = soup.select_one("a.coTableNaviNextPage")["href"]
#main_url = base_url + main_url

pageNr = 1
#main_url = furl(main_url)

main_url = r.url
lectures = []

while True:
    #main_url.args["pPageNr"] = pageNr
    print(main_url)
    r = s.get(main_url)
    #root = ET.fromstring(r.content)
    #content = root.find("./instruction[@action='replaceElement']").text
    content = r.content
    soup = BeautifulSoup(content, "html.parser")

    tr_lectures = soup.find_all("tr", {"class": "coTableR"})
    if len(tr_lectures) == 0:
        break

    for l in tr_lectures:
        column = l.find_all("td")
        lecture_type = column[4].text.strip()
        info = column[2].find_all("span")
        name = info[0].text
        group = info[3].text
        id = column[2].find("a")["href"].split("/")[-1].split("?")[0]

        lectures.append({
            "id": id,
            "type": lecture_type,
            "name": name,
            "group": group
        })
    pageNr += 1
    break

lectures.sort(key=lambda x: (x["name"], x["type"]))

strings = ["{}: {} - {}".format(l["type"], l["name"], l["group"]) for l in lectures]

i = ratools.list_index_selector(strings)

out_file_name = strings[i] + ".csv"

id = lectures[i]["id"]
lecture_url = "https://online.medunigraz.at/mug_online/pl/ui/$ctx/wbTermin_List.wbLehrveranstaltung?pStpSpNr=" + id
r = s.get(lecture_url, headers={"accept": "application/json"})
soup = BeautifulSoup(r.content, "html.parser")
soup = soup.select("#tabLvTermine")[0].find("tbody")

with open(out_file_name, "w") as out_file:
    for r in soup.find_all("tr"):
        cols = r.find_all("td")
        if len(cols) == 1:
            if lectures[i]["group"] == cols[0].text:
                active = True
            else:
                active = False
        elif active:
            date = cols[1].text.strip()
            parse_string = '%H:%M'
            d_from = datetime.datetime.strptime(cols[2].text.strip(), parse_string)
            d_to = datetime.datetime.strptime(cols[3].text.strip(), parse_string)
            if ": " in cols[7].text:
                lect_type, lect = cols[7].text.strip().split(": ", 1)
            else:
                lect_type = "VO"
                lect = cols[7].text
            prof = cols[8].text.strip()
            out_file.write("{};{};{};{}\n".format(date, int((d_to - d_from).total_seconds() / 60 / 45), lect, prof))

exit(0)

with open(out_file_name, "w") as out_file:
    soup = soup.select("tr.coTableR")
    out_file.write(str(soup))
    exit(0)

lecture_url = "https://online.medunigraz.at/mug_online/ee/rest/slc.tm.cp/student/courseGroups/firstGroups/" + \
              lectures[i]["id"]
r = s.get(lecture_url, headers={"accept": "application/json"})
content = r.json()

lecture_url = "https://online.medunigraz.at/mug_online/ee/rest/slc.tm.cp/student/courseGroups/remainingGroups/" + \
              lectures[i]["id"]
r = s.get(lecture_url, headers={"accept": "application/json"})
content2 = r.json()
content["resource"].extend(content2["resource"])

group = lectures[i]["group"]

with open(out_file_name, "w") as out_file:
    for r in content["resource"]:
        n = r["content"]["cpCourseGroupDto"]["name"]
        if group != n:
            continue

        for f in r["content"]["cpCourseGroupDto"]["appointmentDtos"]:
            parse_string = '%Y-%m-%dT%H:%M:%S'
            d_from = datetime.datetime.strptime(f["timestampFrom"]["value"], parse_string)
            d_to = datetime.datetime.strptime(f["timestampTo"]["value"], parse_string)

            prof = ""
            if len(f["appointmentLectureshipDto"]) > 0:
                prof = f["appointmentLectureshipDto"][0]["identityLibDto"]["lastName"].strip()
            lect = ""
            lect_type = ""
            if "learningUnit" in f:
                lect = f["learningUnit"]
                lect_type, lect = lect.split(":", 1)
            lect = lect.strip()
            lect_type = lect_type.strip()
            out_file.write(
                "{};{};{};{};{}\n".format(lect_type, lect, int((d_to - d_from).total_seconds() / 60 / 45), prof,
                                          d_from.date()))

print("Finished.")
