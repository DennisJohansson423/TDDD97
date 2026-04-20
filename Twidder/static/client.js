window.onload = function () {
    displayView();
};


// Email-validering
function isValidEmail(email) {
    return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);
}

// WebSocket, kopplas upp när användaren är inloggad
let socket = null;

function connectSocket() {
    const token = localStorage.getItem("token");
    if (!token) return;

    // Undvik dubbelkoppling
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        return;
    }

    const scheme = (window.location.protocol === "https:") ? "wss" : "ws";
    socket = new WebSocket(scheme + "://" + window.location.host + "/ws");

    socket.onopen = function () {
        // Servern förväntar sig token som första meddelande
        socket.send(token);
    };

    socket.onmessage = function (event) {
        let msg;
        try { msg = JSON.parse(event.data); } catch (e) { return; }

        // Servern säger åt oss att logga ut (någon annan loggade in)
        if (msg.type === "logout") {
            alert("Du har blivit utloggad eftersom du loggade in någon annanstans.");
            logout(true);
        }
    };

    socket.onclose = function () {
        socket = null;
    };
}


function disconnectSocket() {
    if (socket) {
        try { socket.close(); } catch (e) {}
        socket = null;
    }
}


// Hjälpfunktion för HTTP-anrop
function apiRequest(method, url, body, callback) {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    xhr.setRequestHeader("Content-Type", "application/json");

    const token = localStorage.getItem("token");
    if (token) {
        xhr.setRequestHeader("Authorization", token);
    }

    // Hantera svar från servern
    xhr.onreadystatechange = function () {
        if (xhr.readyState === 4) {
            let resp;
            try {
                resp = JSON.parse(xhr.responseText);
            } catch (e) {
                resp = { message: "Bad JSON from server.", data: null };
            }

            if (xhr.status === 500) {
                console.error("Server error.");  
            } else if (xhr.status === 405) {
                console.error("Method not allowed.");
            }
            
            callback(resp, xhr.status);
        }
    };

    xhr.send(body ? JSON.stringify(body) : null);
}


// Vy-hantering, visar welcomeview om ingen giltig token finns annars profilview
function displayView() {
    const token = localStorage.getItem("token");
    const content = document.getElementById("content");

    // Ingen token -> welcome
    if (!token) {
        content.innerHTML = document.getElementById("welcomeview").innerHTML;
        return;
    }

    // Token finns -> varifiera med server innan profilview visas
    apiRequest("GET", "/get_user_data_by_token", null, function (res, status) {
        if (status !== 200) {
            localStorage.removeItem("token");
            disconnectSocket();
            content.innerHTML = document.getElementById("welcomeview").innerHTML;
            return;
        }

        content.innerHTML = document.getElementById("profileview").innerHTML;
        openTab('homePanel', 'tabButtonHome');
        loadUserData();
        reloadWall();
        connectSocket();
    });
}


// Inloggning, validerar input och anropar /sign_in
// Vid lyckad inloggning sparas token i localStorage och profileview visas
function validateSignIn() {
    const email = document.getElementById("loginEmail").value;
    const password = document.getElementById("loginPassword").value;
    const feedbackElement = document.getElementById("signin_message");

    // Validera email-format
    if (!isValidEmail(email)) {
        feedbackElement.style.color = "red";
        feedbackElement.innerHTML = "Invalid email format.";
        return;
    }

    if (password.length < 8) {
        feedbackElement.style.color = "red";
        feedbackElement.innerHTML = "Password too short (min 8 chars).";
        return;
    }

    apiRequest("POST", "/sign_in", { username: email, password: password }, function (res, status) {
        if (status === 200) {
            localStorage.setItem("token", res.data);
            displayView();
            connectSocket();
        } else if (status === 401) {
            feedbackElement.style.color = "red";
            feedbackElement.innerHTML = "Incorrect email or password.";
        } else if (status === 400) {
            feedbackElement.style.color = "red";
            feedbackElement.innerHTML = "FIll in all fields.";
        } else {
            feedbackElement.style.color = "red";
            feedbackElement.innerHTML = "An error occurred. Please try again.";
        }
    });
}


// Registrering, validerar lösenord och anropar /sign_up
// Visar serverns svar i signup_message
function validateSignUp() {
    const password = document.getElementById("signupPassword").value;
    const repeatPassword = document.getElementById("signupRepeatPassword").value;
    const feedbackElement = document.getElementById("signup_message");

    const email = document.getElementById("signupEmail").value;

    // Validera email-format
    if (!isValidEmail(email)) {
        feedbackElement.style.color = "red";
        feedbackElement.innerHTML = "Invalid email format.";
        return;
    }

    if (password.length < 8) {
        feedbackElement.style.color = "red";
        feedbackElement.innerHTML = "Password too short (min 8 chars).";
        return;
    }
    if (password !== repeatPassword) {
        feedbackElement.style.color = "red";
        feedbackElement.innerHTML = "Passwords do not match!";
        return;
    }

    const user = {
        email: email,
        password: password,
        firstname: document.getElementById("signupFirstname").value,
        familyname: document.getElementById("signupFamilyname").value,
        gender: document.getElementById("signupGender").value,
        city: document.getElementById("signupCity").value,
        country: document.getElementById("signupCountry").value
    };

    apiRequest("POST", "/sign_up", user, function (res, status) {
        if (status === 201) {
            feedbackElement.style.color = "green";
            feedbackElement.innerHTML = "Registration successful! You can now log in.";
            document.getElementById("signupEmail").value = "";
            document.getElementById("signupPassword").value = "";
            document.getElementById("signupFirstname").value = "";
            document.getElementById("signupFamilyname").value = "";
            document.getElementById("signupCity").value = "";
            document.getElementById("signupCountry").value = "";
            document.getElementById("signupRepeatPassword").value = "";
        } else if (status === 409) {
            feedbackElement.style.color = "red";
            feedbackElement.innerHTML = "Email already registered.";
        } else if (status === 400) {
            feedbackElement.style.color = "red";
            feedbackElement.innerHTML = "Could not register. Please fill in all fields correctly.";
        } else {
            feedbackElement.style.color = "red";
            feedbackElement.innerHTML = "An error occurred. Please try again.";
        }
    });
}


/* Om email är null -> Ladda min egen info (Home)
Om email skickas med -> Ladda deras info (Browse) */
function loadUserData(email) {
    if (typeof email === 'undefined') { email = null; }

    if (email === null) {
        apiRequest("GET", "/get_user_data_by_token", null, function (res, status) {
            if (status !== 200) {
                logout(true);
                return;
            }
            const data = res.data;
            document.getElementById("displayFirstname").innerText = data.firstname;
            document.getElementById("displayFamilyname").innerText = data.familyname;
            document.getElementById("displayEmail").innerText = data.email;
            document.getElementById("displayCity").innerText = data.city;
            document.getElementById("displayCountry").innerText = data.country;
        });
    } else {
        apiRequest("GET", "/get_user_data_by_email/" + encodeURIComponent(email), null, function (res, status) {
            if (status === 200) {
                const data = res.data;
                document.getElementById("browseFirstname").innerText = data.firstname;
                document.getElementById("browseFamilyname").innerText = data.familyname;
                document.getElementById("browseEmailDisplay").innerText = data.email;
                document.getElementById("browseCity").innerText = data.city;
                document.getElementById("browseCountry").innerText = data.country;

                document.getElementById("browseResult").style.display = "block";
                document.getElementById("browse_error_message").innerHTML = "";
            } else if (status === 404) {
                document.getElementById("browse_error_message").innerText = "User not found.";
                document.getElementById("browseResult").style.display = "none";
            } else if (status === 401) {
                logout(true);
                return;
            } else {
                document.getElementById("browse_error_message").innerText = res.message;
                document.getElementById("browseResult").style.display = "none";
            }
        });
    }
}


/* Om email är null -> Ladda min egen wall (Home)
   Om email skickas med -> Ladda deras wall (Browse) */
function reloadWall(email) {
    if (typeof email === 'undefined') { email = null; }

    let endpoint;
    let wallDiv;

    if (email === null) {
        endpoint = "/get_user_messages_by_token";
        wallDiv = document.getElementById("homeWallMessages");
    } else {
        endpoint = "/get_user_messages_by_email/" + encodeURIComponent(email);
        wallDiv = document.getElementById("browseWallMessages");
    }

    wallDiv.innerHTML = "";

    apiRequest("GET", endpoint, null, function (res, status) {
        if (status !== 200) {
            if (status === 401) {
                logout(true);
            }
            return;
        }

        const messages = res.data;
        for (let i = 0; i < messages.length; i++) {
            const msg = messages[i];
            const msgHtml = "<div class='message-item'>" +
                "<div class='message-author'>" + msg.writer + " wrote:</div>" +
                "<div class='message-text'>" + msg.content + "</div>" +
                "</div>";
            wallDiv.innerHTML += msgHtml;
        }
    });
}


// Söker upp en användare i Browse genom email och laddar deras data + wall
function browseUser() {
    const email = document.getElementById("browseEmail").value.trim();
    if (!email) return;
    loadUserData(email);
    reloadWall(email);
}


// Postar ett meddelande på Home wall
function postToHomeWall() {
    const text = document.getElementById("homeWallInput").value.trim();
    if (text === "") return;

    apiRequest("GET", "/get_user_data_by_token", null, function (res, status) {
        if (status !== 200) { logout(true); return; }
        const myEmail = res.data.email;

        apiRequest("POST", "/post_message", { email: myEmail, message: text }, function (r2, status2) {
            if (status2 === 201) {
                document.getElementById("homeWallInput").value = "";
                reloadWall();
            } else if (status2 === 404) {
                alert("User not found.");
            } else if (status2 === 400) {
                alert("Could not post message. Please try again.");
            } else {
                alert("An error occurred. Please try again.");
            }
        });
    });
}


// Postar ett meddelande på den användare som just nu visas i Browse
function postToBrowseWall() {
    const text = document.getElementById("browseWallInput").value.trim();
    if (text === "") return;

    const recipientEmail = document.getElementById("browseEmailDisplay").innerText.trim();
    if (!recipientEmail) return;

    apiRequest("POST", "/post_message", { email: recipientEmail, message: text }, function (res, status) {
        if (status === 201) {
            document.getElementById("browseWallInput").value = "";
            reloadWall(recipientEmail);
        } else if (status === 404) {
            alert("User not found.");
        } else if (status === 400) {
            alert("Could not post message. Please try again.");
        } else {
            alert("An error occurred. Please try again.");
        }
    });
}


// Visar vald panel (Home/Browse/Account) och markerar aktiv knapp
function openTab(panelId, buttonId) {
    const contents = document.getElementsByClassName("tab-content");
    for (let i = 0; i < contents.length; i++) {
        contents[i].style.display = "none";
    }
    const buttons = document.getElementsByClassName("tab-button");
    for (let i = 0; i < buttons.length; i++) {
        buttons[i].classList.remove("active");
    }
    document.getElementById(panelId).style.display = "block";
    document.getElementById(buttonId).classList.add("active");
}


// Validerar att nya lösenorden matchar och anropar /change_password
function changePassword() {
    const oldPass = document.getElementById("oldPassword").value;
    const newPass = document.getElementById("newPassword").value;
    const repeatPass = document.getElementById("repeatNewPassword").value;
    const msgArea = document.getElementById("password_message");

    msgArea.innerHTML = "";

    if (newPass !== repeatPass) {
        msgArea.style.color = "red";
        msgArea.innerHTML = "New passwords do not match!";
        return;
    }

    apiRequest("PUT", "/change_password", { oldpassword: oldPass, newpassword: newPass }, function (res, status) {
        if (status === 200) {
            msgArea.style.color = "green";
            msgArea.innerHTML = res.message;
            document.getElementById("oldPassword").value = "";
            document.getElementById("newPassword").value = "";
            document.getElementById("repeatNewPassword").value = "";
        } else if (status === 400) {
            msgArea.style.color = "red";
            msgArea.innerHTML = "Wring old password or invalid new password.";
        } else if (status === 401) {
            msgArea.style.color = "red";
            msgArea.innerHTML = "You are not logged in.";
        } else {
            msgArea.style.color = "red";
            msgArea.innerHTML = "An error occurred. Please try again.";
        }
    });
}


/* silent=true -> använd när token redan är ogiltig
Vid normal logout skickas token till /sign_out så servern kan ta bort raden i loggedin_users */
function logout(silent) {
    const token = localStorage.getItem("token");

    if (silent || !token) {
        disconnectSocket();
        localStorage.removeItem("token");
        displayView();
        return;
    }

    const xhr = new XMLHttpRequest();
    xhr.open("DELETE", "/sign_out", true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.setRequestHeader("Authorization", token);

    xhr.onreadystatechange = function () {
        if (xhr.readyState === 4) {
            disconnectSocket();
            localStorage.removeItem("token");
            displayView();
        }
    };

    xhr.send(null);
}