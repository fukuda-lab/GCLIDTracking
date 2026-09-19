# GCLID-Tracking

# Setup Guide

## Step 1: Install Dependencies

Run the installation script:

```bash
./install.sh
```

---

## Step 2: Install PostgreSQL

PostgreSQL is required for this project, please install before process next steps.

Follow the official guide:
https://www.postgresql.org/download/

After installation, make sure PostgreSQL is running and accessible on your system.

---

## Step 3: Create Database


Run the database setup script:

```bash
python3 createDB.py
```

Then provide the required information:

* Postgres host (default: `localhost`)
* Port (default: `5432`)
* Username
* Password
* Database name

The script will:

* Create the database
* Create all required tables


---

# Run the Program

## Step 1: Train Browser Profile

Run the training script:

```bash
python3 training.py --training-sites listTrain10.txt --output-name training_profile
```

### Notes:

* `listTrain10.txt`: contains training websites (e.g., first 10 domains from Tranco Top)
* The script will:

  * Open Chrome with the extension
  * Visit each site
  * Simulate scrolling behavior
  * Save a trained browser profile as a `.zip` file in the `profiles/` folder

---

## Step 2: Run Ads Crawler

```bash
python3 adcrawler.py \
  --sites listNews_sophos.txt \
  --country JP \
  --profile-zip training_profile.zip \
  --max-pages 4
  
```

### Notes:

* `--sites`: file containing list of target websites
* `--country`: Crawling location, country code, e.g. `US, DE, JP, AU, BR, ZA`
* `--profile-zip`: trained profile generated from Step 1 (stored in `profiles/`)
* `--max-pages`: maximum number of pages to crawl per website, including the homepage
* `--headless`: optional, runs the browser without a visible UI

---

## Step 3: Filter Google Ads URLs (gclid)

```bash
python3 FilterAdsUrl.py
```

### Output:

* `O_selected_adsURL.csv` → filtered Google Ads URLs containing `gclid`
* Other optional output files may also be generated


---

## Step 4: Visit Filtered Ads URLs

```bash
python3 visitAdsUrl.py \
  --sites O_selected_adsURL.csv \
  --country JP \
  --run-no 1
```

---

### Parameters

* `--sites`
  CSV file generated from Step 3 (`O_selected_adsURL.csv`)

* `--country`
  One of: `US, DE, JP, AU, BR, ZA`

* `--run-no`
  Run index (used for repeated experiments)

* `--headless` *(optional)*
  Run browser without UI


---

### What This Step Does

For each Ads URL:

1. Launches a browser instance
2. Clears cookies and cache before visiting
3. Visits the Ads URL
4. Interacts with cookie banners:
    * No interaction
    * Accept all
    * Reject all
5. Records:
   * Final redirected URL
   * Network requests
   * Cookies
6. Stores all data into PostgreSQL

---

### Important Notes

* Browser may restart automatically if it gets stuck (watchdog mechanism)
* Each URL is processed independently
* Ensure database is running before executing this step
---

# Data Analysis

## Analysis 1: 1st-Party Cookies containing `gclid`

```bash
python3 DP_getStCookieGCLID.py
```

---

## Analysis 2: 3rd-Party Tracking Cookies

```bash
python3 DP_getRdCookieTracking.py
```

---

## Analysis 3: GCLID Leakage via Network Requests

### Step 1: Identify Tracking Requests

```bash
python3 DP_setTrackingRequest.py --re2
```

---

### Step 2: Extract GCLID Leakage

```bash
python3 DP_getGCLIDLeakage.py --tracking
```


### Description:

This step:

* Extracts `gclid` values from Google Ads URLs
* Searches for leakage in:

  * Request URLs
  * Headers (Referer, Cookie)
  * Request/response payloads
* Identifies **3rd-party domains receiving gclid**

---

## Done

Full pipeline:

1. Setup environment
2. Setup database
3. Train browser profile
4. Crawl ads
5. Filter Google Ads URLs
6. Visit Ads URLs
7. Analyze:

   * 1st-party cookies (`gclid`)
   * 3rd-party tracking cookies
   * GCLID leakage:

     * Tracking classification
     * Leakage channels & domains

---

- **dataset/**: contains the exported CSV data used in the study.  
- **gclid_analysis/**: contains analysis scripts and figures generated from the dataset.