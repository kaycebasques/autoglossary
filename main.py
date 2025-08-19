from pathlib import Path
from string import Template
from threading import Thread
import glob
import subprocess
import sys

from google import genai
import tomlkit


REPO_NAME = "repo"


def get_config():
    with open("config.toml", "r") as f:
        config = tomlkit.parse(f.read())
    return config


def run(command):
    return subprocess.run(command, text=True, capture_output=True)


def clone(url):
    run(["git", "clone", "--depth", "1", url, REPO_NAME])


def setup_repo():
    config = get_config()
    if not Path(REPO_NAME).exists():
        print("[INFO] No repo found, cloning new")
        clone(config["repo"])
        return
    result = run(["git", "-C", REPO_NAME, "remote", "get-url", "origin"])
    url = result.stdout.strip()
    if url == config["repo"]:
        print("[INFO] Repo is ready")
        return
    print("[INFO] Removing old repo and cloning new")
    shutil.rmtree(REPO_NAME)
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


def analyze(template, doc):
    # TODO: Checkpoints
    print(doc)


def process(docs):
    template = load_template()
    start = 0
    max_threads = 10
    while start < len(docs):
        threads = []
        for i in range(start, start + max_threads):
            if i >= len(docs):
                continue
            doc = docs[i]
            thread = Thread(target=analyze, kwargs={"template": template, "doc": doc})
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        start += max_threads


setup_repo()
glossary = load_glossary()
docs = list_docs()
process(docs)
