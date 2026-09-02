--
-- PostgreSQL database cluster dump
--

\restrict uivGOy8AQtZuckKyLXea8PCKmClkaENpJjgt1Hg8daxmSE0CIDdbqZcUVc7YwR4

SET default_transaction_read_only = off;

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

--
-- Roles
--

CREATE ROLE migrator;
ALTER ROLE migrator WITH SUPERUSER INHERIT CREATEROLE CREATEDB LOGIN REPLICATION BYPASSRLS PASSWORD 'SCRAM-SHA-256$4096:BRd33cleWZ+lwSW2nQ0YDg==$f5gOzp/ZvsLY6Y1bsnEI6qegLhZ+h3MKHYgYs4xVe+s=:AGG5m++k7/ndHCYg5ofd8UUFpSY853X1B5K4yUQeeq4=';

--
-- User Configurations
--








\unrestrict uivGOy8AQtZuckKyLXea8PCKmClkaENpJjgt1Hg8daxmSE0CIDdbqZcUVc7YwR4

--
-- PostgreSQL database cluster dump complete
--

