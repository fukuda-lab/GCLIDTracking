-- DROP TABLE IF EXISTS
--     network_response_extra_info,
--     network_responses,
--     network_request_extra_info,
--     network_requests,
--     consent_banners,
--     cookies,
--     local_storage,
--     session_storage,
--     sites
-- CASCADE;

CREATE TABLE sites (
    id_site        SERIAL PRIMARY KEY,
    domain_url     TEXT NOT NULL,
    reached_url    TEXT,
    id_csv         INT,
    country        VARCHAR(8),
    run_no         INT,
    choice         INT,
    crawl_date     DATE,
    crawl_time     TIME,
    crawl_status   TEXT,
    error_message  TEXT,
    ip             TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE network_requests (
    request_id         SERIAL PRIMARY KEY,

    id_site            INT NOT NULL,

    id_csv         INT,
    country        VARCHAR(8),
    run_no         INT,
    choice         INT,

    page_url           TEXT,

    request_url        TEXT NOT NULL,
    method             VARCHAR(16),
    resource_type      VARCHAR(64),

    headers            TEXT,
    -- payload            TEXT,
    -- cookies            TEXT,

    post_data          TEXT,

    cdp_request_id     TEXT,

    initiator          TEXT,

    is_after           BOOLEAN DEFAULT FALSE,

    timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    easylist            BOOLEAN,
    privacylist         BOOLEAN,
    is_third_party      BOOLEAN,

    CONSTRAINT fk_netreq_site
        FOREIGN KEY (id_site)
        REFERENCES sites(id_site)
        ON DELETE CASCADE
);

CREATE TABLE network_request_extra_info (
    id SERIAL PRIMARY KEY,

    cdp_request_id TEXT NOT NULL,
    id_site        INT NOT NULL,
    id_csv         INT,
    country        VARCHAR(8),
    run_no         INT,
    choice         INT,

    headers        TEXT,
    cookies        TEXT,
    blocked_reasons TEXT,

    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,


    FOREIGN KEY (id_site)
        REFERENCES sites(id_site)
        ON DELETE CASCADE
);


CREATE TABLE network_responses (
    response_id        SERIAL PRIMARY KEY,
    cdp_request_id     TEXT,
    response_url        TEXT,

    id_site            INT NOT NULL,
    id_csv         INT,
    country        VARCHAR(8),
    run_no         INT,
    choice         INT,

    status_code        TEXT,
    status_text        VARCHAR(255),

    headers            TEXT,

    -- body               TEXT,
    response_body      TEXT,

    mime_type          VARCHAR(255),

    from_cache         BOOLEAN,

    is_after           BOOLEAN DEFAULT FALSE,

    timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,



    CONSTRAINT fk_netres_site
        FOREIGN KEY (id_site)
        REFERENCES sites(id_site)
        ON DELETE CASCADE
);

CREATE TABLE network_response_extra_info (
    id SERIAL PRIMARY KEY,

    cdp_request_id TEXT NOT NULL,
    id_site        INT NOT NULL,
    id_csv         INT,
    country        VARCHAR(8),
    run_no         INT,
    choice         INT,

    headers        TEXT,
    cookies        TEXT,
    blocked_reasons TEXT,

    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (id_site)
        REFERENCES sites(id_site)
        ON DELETE CASCADE
);


CREATE TABLE consent_banners (
    consent_id       SERIAL PRIMARY KEY,

    id_site          INT NOT NULL,
    id_csv         INT,
    country        VARCHAR(8),
    run_no         INT,
    choice          INT,
    domain_url       VARCHAR(255),

    cmp_name         VARCHAR(255),
    user_choice      VARCHAR(32),

    html_snippet     TEXT,
    more_information TEXT,

    detected_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_consent_site
        FOREIGN KEY (id_site)
        REFERENCES sites(id_site)
        ON DELETE CASCADE
);

CREATE TABLE cookies (
    cookie_id      SERIAL PRIMARY KEY,

    id_site        INT NOT NULL,

    id_csv         INT,
    country        VARCHAR(8),
    run_no         INT,
    choice          INT,

    name           TEXT NOT NULL,
    value          TEXT,
    domain         TEXT,
    path           TEXT,

    expires DOUBLE PRECISION,
    expires_convert TEXT,

    is_secure      BOOLEAN DEFAULT FALSE,
    is_http_only   BOOLEAN DEFAULT FALSE,

    session BOOLEAN,

    same_site      TEXT DEFAULT 'None',
    priority TEXT,
    size INTEGER,
    source_port INTEGER,
    source_scheme TEXT,

    partition_key  TEXT DEFAULT 'None',

    is_after       BOOLEAN DEFAULT FALSE,

    current_domain TEXT NOT NULL,
    current_url    TEXT NOT NULL,

    origin TEXT,

    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_cookie_site
        FOREIGN KEY (id_site)
        REFERENCES sites(id_site)
        ON DELETE CASCADE
);



CREATE TABLE local_storage (
    lstorage_id     SERIAL PRIMARY KEY,

    id_site        INT NOT NULL,

    id_csv         INT,
    country        VARCHAR(8),
    run_no         INT,
    choice          INT,

    lstorage_key     TEXT NOT NULL,
    lstorage_value   TEXT,

    is_after       BOOLEAN DEFAULT FALSE,

    current_domain TEXT NOT NULL,
    current_url    TEXT NOT NULL,

    origin TEXT,

    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_local_storage_site
        FOREIGN KEY (id_site)
        REFERENCES sites(id_site)
        ON DELETE CASCADE
);

CREATE TABLE session_storage (
    sstorage_id     SERIAL PRIMARY KEY,

    id_site        INT NOT NULL,

    id_csv         INT,
    country        VARCHAR(8),
    run_no         INT,
    choice          INT,

    sstorage_key     TEXT NOT NULL,
    sstorage_value   TEXT,

    is_after       BOOLEAN DEFAULT FALSE,

    current_domain TEXT NOT NULL,
    current_url    TEXT NOT NULL,

    origin TEXT,

    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_session_storage_site
        FOREIGN KEY (id_site)
        REFERENCES sites(id_site)
        ON DELETE CASCADE
);



CREATE INDEX idx_netreq_site_cdp
ON network_requests(id_site, cdp_request_id);

CREATE INDEX idx_netres_site_cdp
ON network_responses(id_site, cdp_request_id);

CREATE INDEX idx_req_extra_cdp
ON network_request_extra_info(id_site, cdp_request_id);

CREATE INDEX idx_res_extra_cdp
ON network_response_extra_info(id_site, cdp_request_id);

CREATE INDEX idx_netreq_cdp
ON network_requests (cdp_request_id);

CREATE INDEX idx_netres_cdp
ON network_responses (cdp_request_id);

CREATE INDEX idx_requests_site
ON network_requests(id_site);

CREATE INDEX idx_responses_status
ON network_responses(status_code);

CREATE INDEX idx_cookie_domain
ON cookies(domain);

CREATE INDEX idx_local_storage_domain
ON local_storage(id_site);

CREATE INDEX idx_session_storage_domain
ON session_storage(id_site);