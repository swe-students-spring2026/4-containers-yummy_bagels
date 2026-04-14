# Yummy Bagels

![Lint-free](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/lint.yml/badge.svg)
<!-- ![ML Client Build]()
![Web App Build]() -->

An application that matches a user's uploaded image to the most similar NYU professor using facial recognition.

---

## 👥 Team

- [Cary Ho](https://github.com/CakeOfThePans)
- [Albert Chen](https://github.com/azc9673)
- [Luke Sribhud](https://github.com/LukeySan)
- [Joy Song](https://github.com/pancake0003)
- [Chen Chen](https://github.com/LoganHund)

---

## ⚙️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/swe-students-spring2026/4-containers-yummy_bagels.git
```

## 2. Environment Variables

Create a `.env` file using the env.example file inside the web-app folder.

---

## 3. Database Setup

Install Docker if not already installed.

Then run:

```
docker run --name mongodb_dockerhub -p 27017:27017 -e MONGO_INITDB_ROOT_USERNAME=admin -e MONGO_INITDB_ROOT_PASSWORD=secret -d mongo:latest
```

The resulting Mongo URI is:

```
mongodb://admin:secret@localhost:27017/
```

---

## 4. Run the Web App

```
cd web-app
python app.py
```