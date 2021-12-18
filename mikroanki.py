import html

from bs4 import BeautifulSoup
from ratools import ratools
import genanki
import glob
import os
import urllib
import datetime

tag_id = 39  # pädiatrie
tag_id = 2  # Thorax
tag_id = 20  # Ortho

os.makedirs("img", exist_ok=True)
for f in glob.glob("*.png"):
    os.remove(f)
for f in glob.glob("*.apkg"):
    os.remove(f)

my_package = None
my_deck = None
my_model = genanki.Model(
    2056521903,
    'MedUniGraz - KnowledgePulse',
    fields=[
        {'name': 'ID'},
        {'name': 'Question'},
        {'name': 'Answer'},
        {'name': 'Extra'},
    ],
    templates=[
        {
            'name': 'Card 1',
            'qfmt': '{{Question}}{{Answer}}',
            'afmt': '{{FrontSide}}<hr id="extra">{{Extra}}<style>.correct {font-weight: bold}</style>',
        },
    ],
    css="""html, body {
  height: 100%;
  margin: 0;
  padding: 20px;
}

.card {
 font-family: arial;
 font-size: 20px;
 text-align: left;
 color: black;
 background-color: white;
}""")

url = "https://mlearning.medunigraz.at/"
s = ratools.get_requests_session()

print("Login...")
user, password = ratools.get_credentials(url)

s.get(url)

data = {
    "password": password,
    "username": user
}
r = s.post(url + "KnowledgePulse/client/login", data=data)
soup = BeautifulSoup(r.content, "html.parser")
e = soup.select_one("#errorDiv")
if e is not None:
    print(e.text.strip())
    exit(1)
print("Login erfolgreich.")

r = s.get(url + "KnowledgePulse/client/subscribed")
soup = BeautifulSoup(r.content, "html.parser")
course_Ids = [cid["href"].replace("course", "")
              for cid in soup.select("a.listSubscribedEntry.ltr")]
for courseId in course_Ids:
    s.post(url + "KnowledgePulse/client/unsubscribePublicContentCourse",
           json={"courseId": courseId})



r = s.get(url + "KnowledgePulse/client/available?tagId={}".format(tag_id))
soup = BeautifulSoup(r.content, "html.parser")
course_Ids = [cid["href"].replace("course", "")
              for cid in soup.select("a.listAvailableEntry")]

img_nr = 0
for courseId in course_Ids:
    questions = {}

    while True:
        r = s.get(url + "KnowledgePulse/client/course" + courseId)
        soup = BeautifulSoup(r.content, "html.parser")
        title = soup.select_one(".course_title").text.strip()

        info = soup.select_one(".course_info").text.strip()

        if soup.select_one("#courseSubscribe") is not None:
            r = s.get(
                url + "KnowledgePulse/client/subscribeCourse?id=" + courseId)
            continue
        if soup.select_one("#courseRepeat") is not None:
            total_questions = int(info.split(
                "und")[1].split("Karte")[0].strip())
            if total_questions == len(questions):
                break
            else:
                r = s.get(url + "KnowledgePulse/client/repeatCourse")
        r = s.get(url + "KnowledgePulse/client/lesson-intro")
        soup = BeautifulSoup(r.content, "html.parser")
        course = soup.select_one(".course_title").text.strip()

        if my_deck is None:
            my_deck = genanki.Deck(1292963141, title)
            my_package = genanki.Package(my_deck)
            print("")
            print(title + " - " + info)
        print(course)

        while True:
            r = s.get(url + "KnowledgePulse/client/learn")
            soup = BeautifulSoup(r.content, "html.parser")
            if soup.select_one(".learn") is not None:
                r = s.get(url + "KnowledgePulse/client/learn")
                soup = BeautifulSoup(r.content, "html.parser")
                if "subscribed" in r.url:
                    break

            id = soup.select_one("#cardid")
            if id is None:
                continue
            id = id.text.strip()

            if id not in questions:
                question = soup.select_one(".question")
                question_imgs = question.select("img.editorImage")
                question = "<p>{}</p>".format(question.text.strip())
                question_img = ""
                if len(question_imgs) > 0:
                    for img in question_imgs:
                        url_parsed = urllib.parse.urlparse(img["src"])
                        query = urllib.parse.parse_qs(url_parsed.query)
                        response = s.get(img["src"])
                        img_nr = int(datetime.datetime.now().timestamp())
                        file_path = os.path.join(
                            "_img_{}_{:05d}.png".format(id, img_nr))
                        file = open(file_path, "wb")
                        file.write(response.content)
                        file.close()
                        img_nr += 1
                        my_package.media_files.append(file_path)
                        question += "<img src=\"{}\"></img>".format(file_path)

                answers = soup.select(".answer")
                answer_imgs = soup.select(".answer img")
                if len(answer_imgs) > 0:
                    for img in answer_imgs:
                        blacklist = [
                            "/KnowledgePulse/img/emptyradio.png", "/KnowledgePulse/img/empty.png"]
                        if img["src"] not in blacklist:
                            print(img)
                            print(blacklist)
                            print("img found")
                answers = [(a.text.strip(), a["id"].strip()) for a in answers]
                context = soup.select_one(".context")
                if context is not None:
                    context_imgs = context.select("img.editorImage")
                    context = soup.select_one(".answer_context")
                    if context is not None:
                        context.select_one(".context_header").decompose()
                        del context.attrs["style"]
                    if len(context_imgs) > 0:
                        for img in context_imgs:
                            url_parsed = urllib.parse.urlparse(img["src"])
                            query = urllib.parse.parse_qs(url_parsed.query)
                            response = s.get(img["src"])
                            img_nr = int(datetime.datetime.now().timestamp())
                            file_path = os.path.join(
                                "_img_{}_{:05d}.png".format(id, img_nr))
                            file = open(file_path, "wb")
                            file.write(response.content)
                            file.close()
                            img_nr += 1
                            my_package.media_files.append(file_path)
                            img["src"] = file_path
                else:
                    context = ""

                print(question)
                for a, aid in answers:
                    print(" - " + a)
                print("")

                r = s.post(url + "KnowledgePulse/client/checkAnswers")

                _, wrong, correct = r.text.split(";")

                solution = correct.split(",")

                questions[id] = {"q": question, "a": answers, "c": context,
                                 "s": solution}

                answers_formated = "<ul>"
                for a, aid in answers:
                    a = html.escape(a)
                    if aid in solution:
                        answers_formated += "<li class=\"correct\">{}</li>".format(
                            a)
                    else:
                        answers_formated += "<li class=\"incorrect\">{}</li>".format(
                            a)
                answers_formated += "</ul>"

                my_note = genanki.Note(model=my_model, fields=[id, question, answers_formated, str(
                    context)], tags=["KnowledgePulse::{}::{}".format(title, course).replace(" ", "_")])
                my_note.guid = genanki.guid_for(courseId, id)

                my_deck.add_note(my_note)
            else:
                print("Hmnnn I know this answer!")
                para = "?answer=" + "&answer=".join(questions[id]["s"])
                r = s.post(url + "KnowledgePulse/client/checkAnswers")
                answered, wrong, correct = r.text.split(";")
                r = s.post(url + "KnowledgePulse/client/checkAnswers" + para)
                answered, wrong, correct = r.text.split(";")
                if wrong != "":
                    print("correct")

    filename = title + '.apkg'
    filename = filename.replace(os.path.sep, "")
    if my_package is not None:
        my_package.write_to_file(filename)
    my_deck = None
