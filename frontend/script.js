let sessionId = null;

async function login() {
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;
    console.log("Sending email:", email);

    const response = await fetch("/login", {
        method: "POST",
        credentials: "include",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ email, password })
    });

    const data = await response.json();

    if (response.status === 200) {
        document.getElementById("auth-message").innerText = "Login successful!";
        document.getElementById("auth-section").style.display = "none";
    } else {
        document.getElementById("auth-message").innerText = data.detail || "Login failed";
    }
}

async function startInterview() {

    const name = document.getElementById("name").value;
    const domain = document.getElementById("domain").value;

    const response = await fetch("/start-session", {
        method: "POST",
        credentials: "include",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            candidate_name: name,
            domain: domain
        })
    });

    const data = await response.json();
    console.log("Start session response:", data);
    sessionStorage.setItem("session_id", data.session_id);

    window.location.href = "/frontend/interview.html";
}


async function submitAnswer() {
    const sessionId = sessionStorage.getItem("session_id");
    const answerText = document.getElementById("answer").value;
    const response = await fetch("/submit-answer", {
        method: "POST",
        credentials: "include",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            answer: answerText,
            session_id: sessionId
        })
    });

    const data = await response.json();

    document.getElementById("feedback").innerText =
        "Score: " + data.score + " | " + data.feedback;

    if (data.next_question) {
        document.getElementById("question").innerText = data.next_question;
        document.getElementById("answer").value = "";
    } else if (data.is_completed) {
        document.getElementById("question").innerText = "Interview Completed!";
    }
}

async function register() {
    const email = document.getElementById("register-email").value;
    const password = document.getElementById("register-password").value;

    console.log("Registering:", email);

    const response = await fetch("/register", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ email, password })
    });

    const data = await response.json();

    if (response.status === 200) {
        document.getElementById("register-message").innerText = "Registered successfully!";
    } else {
        document.getElementById("register-message").innerText = data.detail || "Registration failed";
    }
}

window.logout = async function () {
    await fetch("/logout", {
        method: "POST",
        credentials: "include"
    });

    sessionStorage.clear();
    alert("Logged out successfully");
    window.location.href = "/";
};

async function loadFirstQuestion() {

    const sessionId = sessionStorage.getItem("session_id");

    console.log("Session ID from storage:", sessionId);

    const response = await fetch(`/session/${sessionId}`, {
        method: "GET",
        credentials: "include"
    });

    const data = await response.json();

    console.log("Session API response:", data);

    document.getElementById("question").innerText = data.current_question;
}

window.onload = function () {

    if (window.location.pathname.includes("interview.html")) {
        loadFirstQuestion();
    }

};