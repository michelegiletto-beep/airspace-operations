-- Additive schema version 2. Store.migrate() applies the same SQLAlchemy definitions.
-- Back up the database, evidence directory and audit key before upgrading.



CREATE TABLE sharing_agreements (
	id VARCHAR NOT NULL, 
	owner_organisation_id VARCHAR NOT NULL, 
	operator_organisation_id VARCHAR NOT NULL, 
	aircraft_id VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	state VARCHAR NOT NULL, 
	terms JSON NOT NULL, 
	offer_actor_id VARCHAR NOT NULL, 
	accepted_actor_id VARCHAR, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_organisation_id) REFERENCES organisations (id), 
	FOREIGN KEY(operator_organisation_id) REFERENCES organisations (id), 
	FOREIGN KEY(aircraft_id) REFERENCES records (id)
)

;

CREATE INDEX ix_sharing_agreements_operator_organisation_id ON sharing_agreements (operator_organisation_id);

CREATE INDEX ix_sharing_agreements_owner_organisation_id ON sharing_agreements (owner_organisation_id);


CREATE TABLE resource_locks (
	resource_key VARCHAR NOT NULL, 
	generation INTEGER NOT NULL, 
	PRIMARY KEY (resource_key)
)

;


CREATE TABLE fleet_reservations (
	id VARCHAR NOT NULL, 
	owner_organisation_id VARCHAR NOT NULL, 
	operator_organisation_id VARCHAR NOT NULL, 
	aircraft_id VARCHAR NOT NULL, 
	agreement_id VARCHAR, 
	schedule_id VARCHAR NOT NULL, 
	mission_id VARCHAR NOT NULL, 
	owner_record_version INTEGER, 
	flight_seconds INTEGER, 
	start VARCHAR NOT NULL, 
	"end" VARCHAR NOT NULL, 
	state VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (schedule_id, mission_id, aircraft_id), 
	FOREIGN KEY(owner_organisation_id) REFERENCES organisations (id), 
	FOREIGN KEY(operator_organisation_id) REFERENCES organisations (id), 
	FOREIGN KEY(aircraft_id) REFERENCES records (id), 
	FOREIGN KEY(agreement_id) REFERENCES sharing_agreements (id), 
	FOREIGN KEY(schedule_id) REFERENCES records (id)
)

;

CREATE INDEX ix_fleet_reservations_operator_organisation_id ON fleet_reservations (operator_organisation_id);

CREATE INDEX ix_fleet_reservations_owner_organisation_id ON fleet_reservations (owner_organisation_id);
