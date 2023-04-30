import time
import glob
import html
import os
import urllib

import genanki
from bs4 import BeautifulSoup
from ratools import ratools

tag_id = 39  # pädiatrie
tag_id = 2  # Thorax
tag_id = 20  # Ortho
tag_id = 40  # Radiologie
tag_id = 15  # Informatik
tag_id = 14  # Derma
tag_id = 29  # Augen
tag_id = 38  # Anästhesie

os.makedirs("img", exist_ok=True)
for f in glob.glob("*.png"):
    os.remove(f)
#for f in glob.glob("*.apkg"):
#    os.remove(f)

my_package = None
my_deck = None
my_model = genanki.Model(
    2056521905,
    'MedUniGraz - KnowledgePulse',
    fields=[
        {'name': 'Question'},
        {'name': 'Answer'},
        {'name': 'QuestionExtra'},
        {'name': 'AnswerExtra'},
        {'name': 'ID'},
    ],
    templates=[
        {
            'name': 'Card 1',
            'qfmt': '{{Question}}{{Answer}}{{QuestionExtra}}',
            'afmt': '{{FrontSide}}<div id="extra">{{AnswerExtra}}</div><style>.correct {font-weight: bold}</style>',
        },
    ],
    css="""html, body {
  height: 100%;
  margin: 0;
  padding: 20px;
}

.card {
 font-family: arial;
 font-size: 24px;
 text-align: center;
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



def process_imgs(div):
    for img in div.select("img"):
        if "class" in img.attrs and "icon" in img["class"]:
            continue
        response = s.get(img["src"])
        img_nr = time.time_ns()
        file_path = os.path.join(
            "_img_{}_{:05d}.png".format(id, img_nr))
        file = open(file_path, "wb")
        file.write(response.content)
        file.close()
        my_package.media_files.append(file_path)
        img["src"] = file_path

def preprocess_html(tag):
    for x in tag.select("div.context_header"):
        x.name = "h1"
def preprocess_imgs(imgs):
    for img in imgs:
        url = img["onclick"].split("'")[1].replace("\\", "")
        new_tag = soup.new_tag("img", src=url)
        img.replaceWith(new_tag)


def tag_children_to_text(question):
    res = []
    for q in question.find_all(True, recursive=False):
        for x in q.find_all(True, recursive=False):
            if q.name == x.name:
                print("now")
        txt = q.text.strip()
        if txt == "" and q.name in ["p"]:
            continue
        res.append(str(q).strip())
    return "\n".join(res)


def process_context(class_name):
    answer = soup.select_one(class_name)
    if answer is None:
        return ""

    image_wrapper = answer.select_one(".imagewrapper")
    answer_imgs = image_wrapper.select("a.intro_image")
    preprocess_imgs(answer_imgs)
    process_imgs(image_wrapper)
    extra_image = tag_children_to_text(image_wrapper)

    context_text = answer.select_one(".context_text")
    context_imgs = context_text.select("a.intro_image")
    preprocess_imgs(context_imgs)
    process_imgs(context_text)
    preprocess_html(context_text)
    extra_text = tag_children_to_text(context_text)

    return extra_image + "\n" + extra_text


for courseId in course_Ids:
    questions = {}
    # new
    course_url = url + "KnowledgePulse/client/course" + courseId
    r = s.get(course_url)
    soup = BeautifulSoup(r.content, "html.parser")
    if soup.select_one("#courseSubscribe") is not None:
        r = s.get(url + "KnowledgePulse/client/subscribeCourse?id=" + courseId)
    else:
        raise Exception("Cannot subscribe.")

    r = s.get(url + "KnowledgePulse/client/index", headers={'referer': course_url})
    soup = BeautifulSoup(r.content, "html.parser")
    title = soup.select_one("#pageTitle").text.strip()
    #if "Fallvig" not in title:
    #    continue
    print("# " + title)
    my_deck = genanki.Deck(1292963141, title)
    my_package = genanki.Package(my_deck)

    lessions = soup.select(".indexlesson")
    lessions.sort(key=lambda x: x.select_one("a.lessonheaderlink").text)

    for lession in lessions:
        course = lession.select_one("a.lessonheaderlink").text.strip()
        print("## " + course)

        question_list = {}

        questions = lession.select("a.indexcard")
        for q in questions:
            if q["href"] == "javascript:;":
                continue
            q_id = q["href"].split("id=")[1]
            r = s.get(url + "KnowledgePulse/client/preview?id={}".format(q_id))
            soup = BeautifulSoup(r.content, "html.parser")
            with open("/tmp/index.html", "wb") as f:
                f.write(r.content)
            id = soup.select_one("#cardid")
            if id is None:
                raise Exception("No card id")
            id = id.text.strip()

            question = soup.select_one(".question")
            question_imgs = question.select(".question_image")
            preprocess_imgs(question_imgs)
            process_imgs(question)
            question = tag_children_to_text(question)

            question_extra = process_context(".question_context")

            extra = process_context(".answer_context")


            if question not in question_list:
                question_list[question] = {"question_extra": question_extra, "answer_extra": extra, "id": id, "answers": {}}

            answers = soup.select(".answer")
            answers = [(a.text.strip(), a["id"].strip()) for a in answers]


            # get correct answers
            r = s.post(url + "KnowledgePulse/client/checkPreviewAnswers?id=" + q_id)
            _, wrong, correct = r.text.split(";")
            solution = correct.split(",")

            for a in answers:
                a_id = a[1]
                correct_answer = a_id in solution
                if a[0] in question_list[question]:
                    assert (question_list[question]["answers"][a[0]] == correct_answer)
                else:
                    question_list[question]["answers"][a[0]] = correct_answer

        for question, question_props in question_list.items():

            answer_extra = question_props["answer_extra"]
            question_extra = question_props["question_extra"]
            question_id = question_props["id"]
            if question.startswith("<p>Welche Aussage(n)") and False: #remove if you want to split answers
                for a, correct in question_props["answers"].items():
                    answer = ""
                    a = html.escape(a)
                    if correct:
                        answer += "<p class=\"correct\">- {}</p>".format(a)
                    else:
                        answer += "<p class=\"incorrect\">- {}</p>".format(a)

                    my_note = genanki.Note(model=my_model, fields=[question, answer, question_extra, answer_extra, question_id],
                                           tags=["KnowledgePulse::{}::{}".format(title, course).replace(" ", "_")])
                    my_note.guid = genanki.guid_for(tag_id, courseId, question_id, a)

                    my_deck.add_note(my_note)
            else:
                answer = ""
                for a, correct in question_props["answers"].items():
                    a = html.escape(a)
                    if correct:
                        answer += "<p class=\"correct\">- {}</p>".format(a)
                    else:
                        answer += "<p class=\"incorrect\">- {}</p>".format(a)

                my_note = genanki.Note(model=my_model, fields=[question, answer, question_extra, answer_extra, question_id],
                                       tags=["KnowledgePulse::{}::{}".format(title, course).replace(" ", "_")])
                my_note.guid = genanki.guid_for(tag_id, courseId, question_id)

                my_deck.add_note(my_note)

    filename = title + '.apkg'
    filename = filename.replace(os.path.sep, "")
    if my_package is not None:
        my_package.write_to_file(filename)
