
-- Drops existing tables
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS loggedin_users;
DROP TABLE IF EXISTS messages;

-- Table to store user information, email is unique identifier
CREATE TABLE users (
    email VARCHAR(100) PRIMARY KEY,
    password VARCHAR(100) NOT NULL,
    firstname VARCHAR(100) NOT NULL,
    familyname VARCHAR(100) NOT NULL,
    gender VARCHAR(20) NOT NULL,
    city VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL
);

-- Table to store active sessions, token is unique identifier
CREATE TABLE loggedin_users (
    token VARCHAR(36) PRIMARY KEY,
    email VARCHAR(100) NOT NULL,
    FOREIGN KEY(email) REFERENCES users(email)
);

-- Table to store messages between users, id is unique identifier
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_email VARCHAR(100) NOT NULL,
    receiver_email VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    FOREIGN KEY(sender_email) REFERENCES users(email),
    FOREIGN KEY(receiver_email) REFERENCES users(email)
);