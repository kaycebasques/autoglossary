from pathlib import Path
from string import Template
from threading import Thread
from typing_extensions import TypedDict
import glob
import json
import shutil
import subprocess
import sys

from google import genai
import tomlkit


REPO_NAME = "repo"
CHECKPOINTS_FILE = "checkpoints.json"
GLOSSARY_FILE = "glossary.json"


def get_config():
    with open("config.toml", "r") as f:
        config = tomlkit.parse(f.read())
    return config


def get_checkpoints():
    with open(CHECKPOINTS_FILE, "r") as f:
        return json.load(f)


def save_checkpoints(data):
    with open(CHECKPOINTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_glossary():
    with open(GLOSSARY_FILE, "r") as f:
        return json.load(f)


def save_glossary(data):
    with open(GLOSSARY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def run(command):
    return subprocess.run(command, text=True, capture_output=True)


def clone(url):
    run(["git", "clone", "--depth", "1", url, REPO_NAME])


def setup_repo():
    config = get_config()
    if not Path(REPO_NAME).exists():
        print("[INFO] No repo found, cloning new")
        clone(config["repo"])
        save_checkpoints([])
        save_glossary({})
        return
    result = run(["git", "-C", REPO_NAME, "remote", "get-url", "origin"])
    url = result.stdout.strip()
    if url == config["repo"]:
        print("[INFO] Repo is ready")
        return
    print("[INFO] Removing old repo and cloning new")
    shutil.rmtree(REPO_NAME)
    save_checkpoints([])
    save_glossary({})
    clone(config["repo"])


def load_template():
    with open("prompt.tmpl", "r") as f:
        template = f.read()
    template = Template(template)
    return template


def load_glossary():
    config = get_config()
    path = Path("repo") / Path(config["glossary"])
    if not path.exists():
        sys.exit("[ERROR] Glossary not found")
    with open(path, "r") as f:
        glossary = f.read()
    return glossary


def list_docs():
    rst = glob.glob(f"{REPO_NAME}/**/*.rst", recursive=True)
    md = glob.glob(f"{REPO_NAME}/**/*.md", recursive=True)
    return rst + md


def populate(template, doc, glossary, guidelines):
    with open(doc, "r") as f:
        src = f.read()
    start = len(f"{REPO_NAME}/")
    doc = doc[start:]
    prompt = template.substitute(doc=doc, src=src, glossary=glossary, guidelines=guidelines)
    class Term(TypedDict):
        id: str
        title: str
        summary: str
        details: str | None
        references: list[str]
    config = {
        "response_mime_type": "application/json",
        "response_schema": list[Term]
    }
    gemini = genai.Client()
    response = gemini.models.generate_content(
        model="gemini-2.5-pro", contents=prompt, config=config
    )
    results: Response = response.parsed
    return results


def should_ignore(doc, paths):
    ignore = False
    for path in paths:
        path = f"{REPO_NAME}/{path}"
        if doc.startswith(path):
            ignore = True
    return ignore


def process(docs):
    template = load_template()
    checkpoints = get_checkpoints()
    glossary = get_glossary()
    config = get_config()
    guidelines = config["guidelines"]
    for doc in docs:
        if doc in checkpoints:
            continue
        if should_ignore(doc, config["ignore"]):
            print(f"ignoring {doc}")
            continue
        if doc == f"{REPO_NAME}/{config['glossary']}":
            continue
        print("=" * len(doc))
        print(doc)
        print("=" * len(doc))
        terms = populate(template, doc, glossary, guidelines)
        if terms is None:
            continue
        for term in terms:
            glossary[term["id"]] = {
                "title": term["title"],
                "summary": term["summary"],
                "details": term["details"],
                "references": term["references"]
            }
            print(f"id: {term['id']}")
            print(f"title: {term['title']}")
            print(f"summary: {term['summary']}")
            print(f"details: {term['details']}")
            print(f"references: {term['references']}")
            print("----------")
        checkpoints.append(doc)
        save_checkpoints(checkpoints)
        save_glossary(glossary)


setup_repo()
glossary = load_glossary()
docs = list_docs()
process(docs)
