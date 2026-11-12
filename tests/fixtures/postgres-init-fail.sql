-- Deliberate failure in an isolated new CI database before application-role init.
-- Never mount this fixture in an operator deployment.
SELECT 1 / 0;
