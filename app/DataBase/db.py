"""
Import the mysql.connector module and establish a connection to 
your MySQL database by providing the necessary credentials
(host, user, password, and database name)
"""

import mysql.connector

try:
    mydb = mysql.connector.connect(
        host="127.0.0.1",  # Or your MySQL server's IP/hostname
        user="root",
        password="Sulochana@522",
        database="doctorfinder_db")
    print("Connection established successfully!")
except mysql.connector.Error as err:
    print(f"Error: {err}")


## Create a Cursor Object and Execute Queries:
if 'mydb' in locals() and mydb.is_connected():
    mycursor = mydb.cursor()
    # mycursor.execute("SELECT * FROM users")
    mycursor.execute("SELECT * FROM search_history")
    # mycursor.execute("SELECT * FROM users")


## Fetch data
if 'mycursor' in locals():
    myresult = mycursor.fetchall()
    for x in myresult:
        print(x)
## Close the connection
if 'mycursor' in locals():
    mycursor.close()
if 'mydb' in locals() and mydb.is_connected():
    mydb.close()
    print("Connection closed.")