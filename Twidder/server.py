"""
server.py

Huvudfilen för Twidder REST API.
Hanterar alla inkommande HTTP-förfrågningar och pratar med databasen via database_helper.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sock import Sock
import database_helper
import re

app = Flask(__name__)
# Tillåter anrop från andra domäner (Cross-Origin Resource Sharing)
CORS(app)
database_helper.init_db(app)

# email -> websocket (en aktiv klient per användare)
sock = Sock(app)
ws_by_email = {}


@app.route("/")
def root():
    """Öppna html via Flask på root."""
    return app.send_static_file("client.html")


@app.route("/sign_up", methods=["POST"])
def sign_up():
    """
    Registrerar en ny användare.
    Förväntar sig JSON med: email, password, firstname, familyname, gender, city, country.
    """
    data = request.get_json()
    if data is None:
        return jsonify({"message": "Missing JSON data.", "data": None}), 400

    email = data.get("email")

    # Kontrollera att alla nödvändiga fält skickades med från klienten
    if not all(
        [
            email,
            data.get("password"),
            data.get("firstname"),
            data.get("familyname"),
            data.get("gender"),
            data.get("city"),
            data.get("country"),
        ]
    ):
        return jsonify(
            {"message": "All fields required.", "data": None}), 400

    # Validera att e-posten har rätt format med hjälp av ett reguljärt uttryck (regex)
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify(
            {"message": "Invalid email format.", "data": None}), 400

    # Kontrollera säkerhetskravet för lösenordets längd
    if len(data.get("password")) < 8:
        return jsonify(
            {"message": "Password too short.", "data": None}), 400

    # Försök spara användaren i databasen
    try:
        if database_helper.create_user(
            email,
            data["password"],
            data["firstname"],
            data["familyname"],
            data["gender"],
            data["city"],
            data["country"],
        ):
            return jsonify(
            {"message": "Succesfully signed up", "data": None}), 201
        else:
            return jsonify(
            {"message": "Database error", "data": None}), 409
        
    except Exception:
        return jsonify(
            {"message": "Internal error", "data": None}), 500


@app.route("/sign_in", methods=["POST"])
def sign_in():
    """
    Loggar in en användare och genererar en token.
    Förväntar sig JSON med: username (email) och password.
    """
    data = request.get_json()

    if data is None:
        return jsonify(
        {"message": "Missing JSON data.", "data": None}), 400

    email = data.get("username")
    password = data.get("password")

    if not email or not password:
        return jsonify(
        {"message": "Missing username or password", "data": None}), 400

    try:
        user = database_helper.get_user_by_email(email)
    except Exception as e:
        print(f"[DB] get_user_by_email failed: {e}")
        return jsonify({"message": "Internal error", "data": None}), 500

    # Kolla om användaren finns och om lösenordet matchar (index 1 är lösenord i databasen)
    if not user or user[1] != password:
        return jsonify(
            {"message": "Wrong username or password.", "data": None}), 401
    # Om användaren redan har en websocket (tex annan flik/dator), logga ut den klienten
    old_ws = ws_by_email.get(email)
    if old_ws is not None:
        try:
            # Informera den gamla klienten och stäng anslutningen
            old_ws.send('{"type":"logout"}')
            old_ws.close()
        except Exception as e:
            # Logga felet så vi inte "sväljer" exception
            print(f"[WS] Failed to logout/close old websocket for {email}: {e}")
        finally:
            # Oavsett vad: ta bort mappingen så den inte pekar på en trasig ws
            ws_by_email.pop(email, None)

    try:
        # Ta bort gamla tokens så bara en session kan vara aktiv
        database_helper.delete_tokens_for_email(email)

        # Skapa ny token
        token = database_helper.create_token(email)
    except Exception as e:
        print(f"[DB] token ops failed for {email}: {e}")
        return jsonify({"message": "Internal error", "data": None}), 500
        
    if not token:
        return jsonify({"message": "Error generating token.", "data": None}), 500
    
    return jsonify({"message": "Successfully signed in.", "data": token}), 200


@app.route("/sign_out", methods=["DELETE"])
def sign_out():
    """
    Loggar ut användaren genom att ta bort deras token från databasen.
    Förväntar sig token i HTTP-headern 'Authorization'.
    """
    token = request.headers.get("Authorization")
    if not token:
        return jsonify(
            {"message": "Missing token.", "data": None}), 400

    try:
        # Om vi kan koppla token -> email, stäng websocket för den användaren
        user = database_helper.get_user_by_token(token)
        if not user:
            return jsonify(
                {"message": "You are not logged in.", "data": None}), 401
        
        email = user["email"]
        old_ws = ws_by_email.get(email)
        if old_ws:  
            try:
                old_ws.close()
            except Exception as e:
                print(f"[WS] Failed to close websocket for {email}: {e}")
            ws_by_email.pop(email, None)

        if database_helper.delete_token(token):
            return jsonify(
                {"message": "Successfully signed out.", "data": None}), 200
        else:
            return jsonify(
                {"message": "Failed to sign out.", "data": None}), 500
        
    except Exception:
        return jsonify(
            {"message": "Internal error", "data": None}), 500


@app.route("/change_password", methods=["PUT"])
def change_password():
    """
    Byter lösenord för en inloggad användare.
    Förväntar sig token i headern och JSON med: oldpassword, newpassword.
    """
    token = request.headers.get("Authorization")
    data = request.get_json()
    if data is None:
        return jsonify(
        {"message": "Missing JSON data", "data": None}), 400

    old_password = data.get("oldpassword")
    new_password = data.get("newpassword")
    if not old_password or not new_password:
        return jsonify(
        {"message": "Missing passwords.", "data": None}), 400

    try:
        # Hämta den inloggade användaren för att veta vems lösenord som ska bytas
        user_data = database_helper.get_user_by_token(token)
        if not user_data:
            return jsonify(
                {"message": "You are not logged in.", "data": None}), 401

        # Hämta användarens kompletta rad i databasen för att kontrollera det gamla lösenordet
        raw_user = database_helper.get_user_by_email(user_data["email"])
        if not raw_user or raw_user[1] != old_password:
            return jsonify(
                {"message": "Wrong old password.", "data": None}), 400

        # Genomför bytet om allting stämmer
        if database_helper.update_password(user_data["email"], new_password):
            return jsonify({"message": "Password changed.", "data": None}), 200
        else:
            return jsonify(
                {"message": "Error changing password.", "data": None}), 500
        
    except Exception:
        return jsonify(
            {"message": "Internal error", "data": None}), 500


@app.route("/get_user_data_by_token", methods=["GET"])
def get_user_data_by_token():
    """
    Hämtar profilinformation för den inloggade användaren (via token).
    Används ofta för 'Home'-fliken i frontend.
    """
    try:
        token = request.headers.get("Authorization")
        user_data = database_helper.get_user_by_token(token)

        if user_data:
            return jsonify(
                {"message": "User data retrieved.", "data": user_data}), 200
        else:
            return jsonify({"message": "Invalid token.", "data": None}), 401
    
    except Exception:
        return jsonify(
            {"message": "Internal error", "data": None}), 500


@app.route("/get_user_data_by_email/<email>", methods=["GET"])
def get_user_data_by_email(email):
    """
    Hämtar profilinformation för en specifik användare via deras email.
    Kräver att personen som gör anropet är inloggad.
    """
    try:
        token = request.headers.get("Authorization")

        # Säkerställ att det är en godkänd (inloggad) användare som snokar
        if not database_helper.get_user_by_token(token):
            return jsonify(
                {"message": "You are not logged in.", "data": None}), 401

        user = database_helper.get_user_by_email(email)
        if user:
            # Omvandla databasens rådata (en tuple) till ett läsbart dictionary
            user_dict = {
                "email": user[0],
                "firstname": user[2],
                "familyname": user[3],
                "gender": user[4],
                "city": user[5],
                "country": user[6],
            }
            return jsonify(
                {"message": "User data retrieved.", "data": user_dict}), 200
        else:
            return jsonify({"message": "User not found.", "data": None}), 404
    
    except Exception:
        return jsonify(
            {"message": "Internal error", "data": None}), 500


@app.route("/get_user_messages_by_token", methods=["GET"])
def get_user_messages_by_token():
    """
    Hämtar alla inlägg från den inloggade användarens egen vägg.
    """
    try:
        token = request.headers.get("Authorization")
        user = database_helper.get_user_by_token(token)

        if user:
            messages = database_helper.get_messages(user["email"])
            return jsonify(
                {"message": "Messages retrieved.", "data": messages}), 200
        else:
            return jsonify({"message": "Invalid token.", "data": None}), 401
    
    except Exception:
        return jsonify(
            {"message": "Internal error", "data": None}), 500


@app.route("/get_user_messages_by_email/<email>", methods=["GET"])
def get_user_messages_by_email(email):
    """
    Hämtar alla inlägg från en annan specifik användares vägg.
    Kräver att den som frågar är inloggad.
    """
    try:
        token = request.headers.get("Authorization")

        if not database_helper.get_user_by_token(token):
            return jsonify(
                {"message": "You are not logged in.", "data": None}), 401

        # Kontrollera först om användaren vi söker faktiskt existerar
        if database_helper.get_user_by_email(email):
            messages = database_helper.get_messages(email)
            return jsonify(
                {"message": "Messages retrieved.", "data": messages}), 200
        else:
            return jsonify({"message": "User not found.", "data": None}), 404
    
    except Exception:
        return jsonify(
            {"message": "Internal error", "data": None}), 500


@app.route("/post_message", methods=["POST"])
def post_message():
    """
    Skriver ett nytt inlägg på en valfri användares vägg.
    Förväntar sig token i headern och JSON med: email (mottagare), message (innehåll).
    """
    token = request.headers.get("Authorization")
    data = request.get_json()
    if data is None:
        return jsonify(
        {"message": "Missing JSON data.", "data": None}), 400

    receiver_email = data.get("email")
    content = data.get("message")

    try:
        # Hämta avsändaren (den inloggade personen)
        sender = database_helper.get_user_by_token(token)
        if not sender:
            return jsonify(
                {"message": "You are not logged in.", "data": None}), 401

        # Validera att fälten inte är tomma
        if not receiver_email or not content:
            return jsonify(
                {"message": "Missing receiver or content.", "data": None}), 400

        # Kontrollera så att mottagaren faktiskt finns i systemet
        if not database_helper.get_user_by_email(receiver_email):
            return jsonify({"message": "User not found.", "data": None}), 404

        # Skapa meddelandet mellan avsändare och mottagare i databasen
        if database_helper.create_message(sender["email"], receiver_email, content):
            return jsonify({ "message": "Message posted.", "data": None}), 201
        else:
            return jsonify(
                {"message": "Error posting message.", "data": None}), 500
    
    except Exception:
        return jsonify(
            {"message": "Internal error", "data": None}), 500


# WebSocket route, klienten kopplar upp och skickar token direkt efter onopen
@sock.route("/ws")
def ws_route(ws):
    # Första meddelandet från klienten ska vara token
    token = ws.receive()
    user = database_helper.get_user_by_token(token) if token else None
    if not user:
        try:
            ws.close()
        except Exception:
            pass
        return

    email = user["email"]

    # Om det redan finns en websocket för samma användare, logga ut den gamla
    old_ws = ws_by_email.get(email)
    if old_ws and old_ws is not ws:
        try:
            old_ws.send('{"type":"logout"}')
            old_ws.close()
        except Exception as e:
            print(f"[WS] Failed to close old websocket for {email}: {e}")
        finally:
            ws_by_email.pop(email, None)
    
    # Spara den aktiva websocketen för den här användaren
    ws_by_email[email] = ws

    # Håll anslutningen vid liv tills klienten disconnectar
    while True:
        msg = ws.receive()
        if msg is None:
            break

    # Städa upp när klienten disconnectar
    if ws_by_email.get(email) is ws:
        ws_by_email.pop(email, None)


@app.teardown_appcontext
def close_connection(exception):
    """
    Stänger databasanslutningen automatiskt när en förfrågan är färdig.
    Detta frigör minne och förhindrar databaslåsningar.
    """
    database_helper.disconnect_db()


if __name__ == "__main__":
    # Starta databasen (kör schema.sql) och kicka igång webbservern
    app.run(debug=True)
