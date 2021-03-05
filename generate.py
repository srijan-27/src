#!/usr/bin/env python3

import datetime
import pprint
import csv
import textwrap
import re
import os

import yaml
from jinja2 import Environment, FileSystemLoader

BASE_FOLDER = "./docs"
POSTFIX = ""
if os.environ.get("LOCAL") == "true":
    POSTFIX = ".html"

def read_csv(path):
    """ Read the pre-process the CSV """
    items = []
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for item in reader:
            item = dict(item)
            if "Abstract" in item:
                item["Abstract_s"] = textwrap.shorten(item.get("Abstract",""), 200-len(item.get("title","")), placeholder="...")
                item["Abstract_m"] = textwrap.shorten(item.get("Abstract",""), 800-len(item.get("title","")), placeholder="...")
            items.append(item)
    return items

def generate_short_url(event, talk):
    import string
    url = "{}_{}_{}_{}".format(
        event.get("name", "").replace(" ", "_"),
        event.get("year", "").replace(" ", "_"),
        talk.get("Name1", "").replace(" ", "_"),
        talk.get("Title", "").replace(" ", "_")
    )
    url = ''.join(filter(lambda x: x in string.printable, url))
    url = re.sub('[\W]+', '', url)
    return url[:100] + POSTFIX

def pick_picture_file(base, pic):
    pic_jpeg = pic.replace(".png", ".jpeg")
    if os.path.isfile(base + pic_jpeg):
        return pic_jpeg
    elif not os.path.isfile(base + pic):
        print("Missing picture: %s%s" % (base, pic))
        return pic


# init the jinja stuff
file_loader = FileSystemLoader("_templates")
env = Environment(loader=file_loader)

# load the context from the metadata file
context = dict()
with open('metadata.yml') as f:
    context = yaml.load(f, Loader=yaml.FullLoader)

# preprocess the events
events = context.get("events")
# sort events by date
events.sort(key=lambda e: e.get("date"))
print("Loaded %s events" % len(events))
for event in events:
    event["short_url"] = event.get("short_url") + POSTFIX

future_events = []
past_events = []
years = dict()
for event in events:
    # sort sponsors
    for sponsor_type in event.get("sponsors", {}).keys():
        event["sponsors"][sponsor_type].sort()
    # divide into past and future events
    if datetime.date.today() > event.get("date"):
        past_events.append(event)
        current_event = event
    else:
        future_events.append(event)
    # bucket by year
    year = str(event.get("date").year)
    event["year"] = year
    if year not in years:
        years[year] = []
    years[year].append(event)
context["future_events"] = future_events
context["past_events"] = past_events
context["current_event"] = past_events[-1]
context["years"] = years

# read the sponsors metadata
try:
    sponsors_list = sorted(read_csv("./_db/sponsors.csv"), key=lambda x: x.get("id"))
    context["sponsors"] = sponsors_list
    context["sponsors_by_id"] = {
        item.get("id"): item for item in sponsors_list
    }
    print("Loaded %d sponsors metadata" % len(context["sponsors"]))
except Exception as e:
    print("Couldn't read sponsors", e)

# pprint.pprint(context)

# generate the subpages
for event in events:
    print("%s %s /%s" % (event.get("date"), event.get("name"), event.get("short_url")))

    # attempt to read the talks CSV
    try:
        talks = read_csv(event.get("db_path"))
    except:
        talks = []
    #talks.sort(key=lambda x: x.get("Title"))

    # check and pick the picture
    event["thumbnail_path"] = pick_picture_file(BASE_FOLDER + "/", event["thumbnail_path"])

    # split into featured and not
    event["talks_featured"] = [talk for talk in talks if talk.get("Featured","").lower() == "yes"]
    event["talks"] = [talk for talk in talks if talk.get("Featured","").lower() != "yes"]

    # extract and store the tracks
    tracks = dict()
    for talk in event["talks"]:
        track = talk.get("Track", "other")
        if track not in tracks:
            tracks[track] = []
        tracks[track].append(talk)
    event["tracks"] = tracks

    # template each talk page for the event
    for talk in talks:

        # check the headshot
        talk["Picture"] = pick_picture_file(BASE_FOLDER + "/assets/headshots/", talk["Picture"])

        # generate things
        talk["short_url"] = generate_short_url(event, talk)
        talk["YouTubeId"] = talk.get("YouTube").split("/")[-1]

        # template the talk subpage
        with open(BASE_FOLDER + "/" + talk.get("short_url").rstrip(".html")  + ".html", "w") as f:
            template = env.get_template("talk.html")
            f.write(template.render(event=event, talk=talk, **context))

    # template the main event page
    with open(BASE_FOLDER + "/" + event.get("short_url").rstrip(".html") + ".html", "w") as f:
        template = env.get_template("event.html")
        f.write(template.render(event=event, **context))

# generate the static bits
for page in ["index.html", "podcast.html", "sponsor.html"]:
    with open(BASE_FOLDER + "/" + page, "w") as f:
        template = env.get_template(page)
        f.write(template.render(page=page, **context))
