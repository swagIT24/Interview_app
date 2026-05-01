let sessionId = null;
let nextQuestionData = null;
/* ================= LOGIN ================= */

async function login() {

    console.log("LOGIN FUNCTION TRIGGERED");

    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    const response = await fetch("/login", {
        method: "POST",
        credentials: "include",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ email, password })
    });

    const data = await response.json();
    localStorage.setItem("refresh_token", data.refresh_token);

    if (response.ok) {

        console.log("Login success");

        // go to dashboard page
       window.location.href = "/frontend/dashboard.html";

    } else {

        console.log("Login failed:", data);

        const message = document.getElementById("auth-message");
        if (message) {
            message.innerText = data.detail || "Login failed";
        }

    }
}


/* ================= START INTERVIEW ================= */

// async function startInterview() {

//     const name = document.getElementById("name").value;
//     const domain = document.getElementById("domain").value;

//     const response = await fetch("/start-session", {
//         method: "POST",
//         credentials: "include",
//         headers: {
//             "Content-Type": "application/json"
//         },
//         body: JSON.stringify({
//             candidate_name: name,
//             domain: domain
//         })
//     });
    

//     const data = await response.json();
//     sessionStorage.setItem("current_question", data.current_question);

//     console.log("Start session response:", data);

//     sessionStorage.setItem("session_id", data.session_id);

//     console.log("Saved session_id:", data.session_id);

//     window.location.href = "/frontend/interview.html";
// }


/* ================= LOAD QUESTION ================= */

// async function loadFirstQuestion() {

//     const sessionId = sessionStorage.getItem("session_id");

//     console.log("Session ID from storage:", sessionId);

//     if (!sessionId) {
//         alert("No interview session found.");
//         window.location.href = "/frontend/index.html";
//         return;
//     }

//     const response = await fetch(`/session/${sessionId}`, {
//         method: "GET",
//         credentials: "include"
//     });

//     if (response.status === 401) {
//         alert("Session expired. Please login again.");
//         window.location.href = "/frontend/index.html";
//         return;
//     }

//     const data = await response.json();

//     console.log("Session API response:", data);

//     document.getElementById("question").innerText =
//         data.current_question;

//     document.getElementById("question-number").innerText =
//         data.current_question_number;

//     document.getElementById("difficulty").innerText =
//         data.difficulty_level;

//     document.getElementById("domain-title").innerText =
//         data.domain + " Interview";

//     document.getElementById("total-questions").innerText =
//         data.total_questions;

/* ================= SUBMIT ANSWER ================= */

window.startInterview = async function () {

    const name = document.getElementById("name").value;
    const domain = document.getElementById("domain").value;

    const response = await fetch("/start-session", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            candidate_name: name,
            domain: domain
        })
    });

    const data = await response.json();

    // store session + question
    sessionStorage.setItem("session_id", data.session_id);
    sessionStorage.setItem("current_question", data.current_question);

    // go to interview page
    window.location.href = "interview.html";
}

async function submitAnswer() {

    const sessionId = sessionStorage.getItem("session_id");
    const answerText = document.getElementById("answer").value;

    if (!answerText.trim()) {
        alert("Please write an answer first");
        return;
    }

    let response = await fetch("/submit-answer", {
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

    // 🔥 HANDLE TOKEN EXPIRED
    if (response.status === 401) {

        console.log("Access token expired, trying refresh...");

        const refreshResponse = await fetch("/refresh-token", {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                refresh_token: localStorage.getItem("refresh_token")
            })
        });

        if (refreshResponse.ok) {

            console.log("Token refreshed, retrying submit...");

            // 🔁 retry original request
            response = await fetch("/submit-answer", {
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

        } else {
            alert("Session expired. Please login again.");
            window.location.href = "/frontend/index.html";
            return;
        }
    }

    const data = await response.json();

    // ✅ store next question for NEXT button
    nextQuestionData = data;

    // ✅ show feedback ONLY
    document.getElementById("feedback").innerText =
        "Score: " + data.score + " | " + data.feedback;

    // ✅ DO NOT update question here anymore
    if (data.next_question) {

        document.getElementById("difficulty").innerText =
            data.difficulty_level;

        //document.getElementById("answer").value = "";

    } else if (data.is_completed) {

        document.getElementById("question").innerText = "Interview Completed!";
    }
}
/* ================= REGISTER ================= */

async function register() {

    const email = document.getElementById("register-email").value;

    const password = document.getElementById("register-password").value;

    const response = await fetch("/register", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ email, password })
    });

    const data = await response.json();

    if (response.ok) {

        document.getElementById("register-message").innerText =
            "Registered successfully!";

    } else {

        document.getElementById("register-message").innerText =
            data.detail || "Registration failed";

    }
}


/* ================= LOGOUT ================= */

window.logout = async function () {

    await fetch("/logout", {
        method: "POST",
        credentials: "include"
    });

    sessionStorage.clear();

    window.location.href = "/frontend/index.html";

};


/* ================= THEME TOGGLE ================= */

const toggleButton = document.getElementById("theme-toggle");

if (toggleButton) {

    toggleButton.addEventListener("click", () => {

        document.body.classList.toggle("dark-mode");

        if (document.body.classList.contains("dark-mode")) {

            localStorage.setItem("theme", "dark");

            toggleButton.innerText = "☀️ Light Mode";

        } else {

            localStorage.setItem("theme", "light");

            toggleButton.innerText = "🌙 Dark Mode";

        }

    });

}

window.addEventListener("load", () => {

    const savedTheme = localStorage.getItem("theme");

    const toggleButton = document.getElementById("theme-toggle");

    if (savedTheme === "dark") {
        document.body.classList.add("dark-mode");
        if (toggleButton) toggleButton.innerText = "☀️ Light Mode";
    } else {
        document.body.classList.remove("dark-mode");   // 🔥 IMPORTANT
        if (toggleButton) toggleButton.innerText = "🌙 Dark Mode";
    }

});


/* ================= TIMER ================= */

// let timeLeft = 600;

// function startTimer(){

//     const timerElement = document.getElementById("time");

//     if(!timerElement) return;

//     setInterval(() => {

//         timeLeft--;

//         const minutes = Math.floor(timeLeft/60);

//         const seconds = timeLeft % 60;

//         timerElement.innerText =
//             `${minutes}:${seconds.toString().padStart(2,"0")}`;

//     },1000)

// }


/* ================= PAGE LOAD ================= */

window.onload = function () {

    if (window.location.pathname.includes("interview.html")) {

        // ✅ Get first question from sessionStorage
        const question = sessionStorage.getItem("current_question");

        if (question) {
            document.getElementById("question").innerText = question;
        }

    }

};
