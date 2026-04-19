# Yummy Bagels


![Lint-free](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/lint.yml/badge.svg)
![Web App Build](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/app-test.yml/badge.svg)
![ML Client Build](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/ml-test.yml/badge.svg)


An application that matches a user's uploaded image to the most similar NYU professor using facial recognition.

---

## 👥 Team

- [Cary Ho](https://github.com/CakeOfThePans)
- [Albert Chen](https://github.com/azc9673)
- [Luke Sribhud](https://github.com/LukeySan)
- [Joy Song](https://github.com/pancake0003)
- [Chen Chen](https://github.com/LoganHund)

---

## Option 1: Quick Start (Recommended)

### Prerequisites
- Docker Desktop installed and running

---

### Run the full system

```bash
docker compose up --build
```

Optional (background mode):

```bash
docker compose up --build -d
```

Stop everything:

```bash
docker compose down
```

Optional (Stop everything and remove volumes):

```bash
docker compose down -v
```

---

### Note:

If the seeding function did not work properly then while the containers are still up, run:

```bash
docker compose exec machine-learning-client python scrape_prof.py
```

and restart the containers:

```bash
docker compose down
docker compose up
```

After starting the system, wait 10–20 seconds before using the web app.
This allows the ML service to seed the database. Using the app too early may result in missing data or errors.

## Access the Services

- Web App → http://localhost:5000

---

## Option 2: Running Services Individually

### MongoDB

```bash
docker run --name mongodb -p 27017:27017 -e MONGO_INITDB_ROOT_USERNAME=admin -e MONGO_INITDB_ROOT_PASSWORD=secret -d mongo:latest
```

---

### Web App

```bash
docker build -t web-app ./web-app

docker run -p 5000:5000 --name web-app -e MONGO_URI="mongodb://admin:secret@host.docker.internal:27017/?authSource=admin" -e MONGO_DBNAME=yummy_bagels -e SECRET_KEY=dev -e ML_SERVICE_URL=http://host.docker.internal:5001/find-lookalike web-app
```

---

### ML Client

```bash
docker build -t machine-learning-client ./machine-learning-client

docker run -p 5001:5001 --name machine-learning-client -e MONGO_URI="mongodb://admin:secret@host.docker.internal:27017/?authSource=admin" -e MONGO_DBNAME=yummy_bagels machine-learning-client
```

---

## Option 3: Run Locally Without Docker (for Development)

### 1. Start MongoDB

```bash
docker run --name mongodb -p 27017:27017 -e MONGO_INITDB_ROOT_USERNAME=admin -e MONGO_INITDB_ROOT_PASSWORD=secret -d mongo:latest
```

---

### 2. Setup Web App

```bash
cd web-app

pip install pipenv

pipenv shell
```

Set environment variables. An example file named `env.example` is given. Copy this into a file named `.env`:

```bash
MONGO_URI="mongodb://admin:secret@localhost:27017/?authSource=admin"
MONGO_DBNAME=yummy_bagels
SECRET_KEY=dev
ML_SERVICE_URL=http://localhost:5001/find-lookalike
```

Run:

```bash
python app.py
```

---

### 3. Setup ML Client

```bash
cd machine-learning-client

pip install pipenv

pipenv shell
```

Set environment variables. An example file named `env.example` is given. Copy this into a file named `.env`:

```bash
MONGO_URI="mongodb://admin:secret@localhost:27017/?authSource=admin"
MONGO_DBNAME=yummy_bagels
```

Run:

```bash
python scrape_prof.py
python client.py
```

`scrape_prof.py` is a seeding function for the database.

---
