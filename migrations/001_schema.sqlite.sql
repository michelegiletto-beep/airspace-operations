-- Schema version1; generated from versioned metadata.

CREATE TABLE idempotency (
	organisation_id VARCHAR NOT NULL, 
	"key" VARCHAR NOT NULL, 
	request_hash VARCHAR NOT NULL, 
	response JSON NOT NULL, 
	PRIMARY KEY (organisation_id, "key")
)

;


CREATE TABLE jobs (
	id VARCHAR NOT NULL, 
	organisation_id VARCHAR NOT NULL, 
	kind VARCHAR NOT NULL, 
	actor_id VARCHAR NOT NULL, 
	state VARCHAR NOT NULL, 
	payload JSON NOT NULL, 
	result JSON, 
	attempts INTEGER NOT NULL, 
	lease_until VARCHAR, 
	deadline VARCHAR, 
	error VARCHAR, 
	version INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE organisations (
	id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	audit_seq INTEGER NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE outbox (
	id VARCHAR NOT NULL, 
	organisation_id VARCHAR NOT NULL, 
	at VARCHAR NOT NULL, 
	topic VARCHAR NOT NULL, 
	payload JSON NOT NULL, 
	delivered_at VARCHAR, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_outbox_organisation_id ON outbox (organisation_id);


CREATE TABLE schema_versions (
	version INTEGER NOT NULL, 
	applied_at VARCHAR NOT NULL, 
	PRIMARY KEY (version)
)

;


CREATE TABLE audit (
	id VARCHAR NOT NULL, 
	organisation_id VARCHAR NOT NULL, 
	sequence INTEGER NOT NULL, 
	actor_id VARCHAR NOT NULL, 
	action VARCHAR NOT NULL, 
	at VARCHAR NOT NULL, 
	payload JSON NOT NULL, 
	previous_hash VARCHAR NOT NULL, 
	hash VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organisation_id, sequence), 
	FOREIGN KEY(organisation_id) REFERENCES organisations (id)
)

;


CREATE TABLE records (
	id VARCHAR NOT NULL, 
	organisation_id VARCHAR NOT NULL, 
	kind VARCHAR NOT NULL, 
	title VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	data JSON NOT NULL, 
	version INTEGER NOT NULL, 
	created_by VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organisation_id) REFERENCES organisations (id)
)

;

CREATE INDEX ix_records_organisation_id ON records (organisation_id);

CREATE INDEX ix_records_kind ON records (kind);


CREATE TABLE users (
	id VARCHAR NOT NULL, 
	organisation_id VARCHAR NOT NULL, 
	email VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	password_hash VARCHAR NOT NULL, 
	disabled INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organisation_id) REFERENCES organisations (id), 
	UNIQUE (email)
)

;


CREATE TABLE record_versions (
	id VARCHAR NOT NULL, 
	organisation_id VARCHAR NOT NULL, 
	record_id VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	snapshot JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (record_id, version), 
	FOREIGN KEY(record_id) REFERENCES records (id)
)

;


CREATE TABLE resource_reservations (
	id VARCHAR NOT NULL, 
	organisation_id VARCHAR NOT NULL, 
	schedule_id VARCHAR NOT NULL, 
	mission_id VARCHAR NOT NULL, 
	resource_kind VARCHAR NOT NULL, 
	resource_id VARCHAR NOT NULL, 
	start VARCHAR NOT NULL, 
	"end" VARCHAR NOT NULL, 
	state VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (schedule_id, mission_id, resource_kind, resource_id), 
	FOREIGN KEY(organisation_id) REFERENCES organisations (id), 
	FOREIGN KEY(schedule_id) REFERENCES records (id)
)

;


CREATE TABLE sessions (
	digest VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	expires_at VARCHAR NOT NULL, 
	PRIMARY KEY (digest), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;