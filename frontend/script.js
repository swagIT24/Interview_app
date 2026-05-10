let sessionId = null;
let nextQuestionData = null;
let currentQuestion = null;
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
    currentQuestion = data.current_question;

    // go to interview page
    window.location.href = "interview.html";
}

async function submitAnswer() {

    const sessionId = sessionStorage.getItem("session_id");
    const answerText = document.getElementById("answer").value;
    console.log("SESSION ID:", sessionId);

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
            session_id: sessionId,
            question_text: currentQuestion
        })
    });

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

            response = await fetch("/submit-answer", {
                method: "POST",
                credentials: "include",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    answer: answerText,
                    session_id: sessionId,
                    question_text: currentQuestion
                })
            });

        } else {
            alert("Session expired. Please login again.");
            window.location.href = "/frontend/index.html";
            return;
        }
    }

    const data = await response.json();
    console.log("SUBMIT RESPONSE:", JSON.stringify(data));

    nextQuestionData = data;

    document.getElementById("feedback").innerText =
        "Score: " + data.score + " | " + data.feedback;

    // ✅ DO NOT update question here anymore
    console.log("NEXT QUESTION:", data.next_question);
    if (data.next_question) {

        nextQuestionData = data;

        document.getElementById("next-btn").style.display = "inline-block";

        document.getElementById("difficulty").innerText =
            data.difficulty_level;

    } else if (data.is_completed) {

        document.getElementById("question").innerText = "Interview Completed!";
    }
}
/* ================= REGISTER ================= */

async function register() {
    console.log("REGISTER FUNCTION RUNNING")
    
    const name = document.getElementById("register-name").value;
    const email = document.getElementById("register-email").value;
    const password = document.getElementById("register-password").value;

    console.log(name)

    const response = await fetch("/register", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({name, email, password })
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

        const question = sessionStorage.getItem("current_question");

        if (question) {
            document.getElementById("question").innerText = question;
            currentQuestion = question;
        }


        const recordBtn = document.getElementById("recordBtn");
        const recordStatus = document.getElementById("recordStatus");
        const answerBox = document.getElementById("answer");

        let mediaRecorder;
        let audioChunks = [];
        let stream;

        let recognition;

        if ('webkitSpeechRecognition' in window) {

            recognition = new webkitSpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = true;

            recognition.onresult = (event) => {
                let transcript = "";

                for (let i = event.resultIndex; i < event.results.length; i++) {
                    transcript += event.results[i][0].transcript;
                }

                answerBox.value = transcript; // live typing
            };

        } else {
            console.log("Speech recognition not supported");
        }

        recordBtn.addEventListener("click", async () => {

            if (!mediaRecorder || mediaRecorder.state === "inactive") {

                // 🎤 Start recording
                stream = await navigator.mediaDevices.getUserMedia({ audio: true });

                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                mediaRecorder.ondataavailable = event => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = () => {

                    const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
                    

                    recordStatus.innerText = "Processing...";

                    const formData = new FormData();
                    formData.append("file", audioBlob, "recording.webm");
                    formData.append("question_text", currentQuestion);  // ← ADD THIS

                    const sessionId = sessionStorage.getItem("session_id");

                    console.log("SESSION ID USED:", sessionId);

                    fetch(`/voice/upload?session_id=${sessionId}`, {
                        method: "POST",
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {

                        console.log("Voice API response:", data);
                        console.log("FULL RESPONSE:", data);

                        // ✅ overwrite with final accurate transcript
                        answerBox.value = data.transcript;

                        document.getElementById("feedback").innerText =
                            "Score: " + data.evaluation.score + " | " + data.evaluation.feedback;
                        
                        if (data.next_question) {
                            nextQuestionData = {
                                next_question: data.next_question,
                                current_question_number: data.evaluation.current_question_number,
                                difficulty_level: data.evaluation.difficulty_level
                            };

                            // Update currentQuestion so text submit also knows
                            currentQuestion = data.next_question;

                            document.getElementById("next-btn").style.display = "inline-block";
                            document.getElementById("difficulty").innerText =
                                data.evaluation.difficulty_level;

                        } else if (data.is_completed) {
                            document.getElementById("question").innerText = "Interview Completed!";
                            document.getElementById("next-btn").style.display = "none";
                        }
                        recordStatus.innerText = "Ready";
                    })
                    .catch(err => {
                        console.error("Error:", err);
                        recordStatus.innerText = "Error";
                    });

                    // 🔐 release mic
                    stream.getTracks().forEach(track => track.stop());
                };

                mediaRecorder.start();

                // 🧠 start real-time transcription
                if (recognition) recognition.start();

                recordStatus.innerText = "Recording...";
                recordBtn.innerText = "⏹ Stop Recording";

            } else {

                // ⏹ Stop recording
                mediaRecorder.stop();

                // 🧠 stop real-time transcription
                if (recognition) recognition.stop();

                recordStatus.innerText = "Stopping...";
                recordBtn.innerText = "🎤 Start Recording";
            }

        });

        document.getElementById("next-btn").addEventListener("click", () => {

            if (!nextQuestionData) return;

            // Update displayed question
            document.getElementById("question").innerText =
                nextQuestionData.next_question;

            // ✅ Save it so submitAnswer can send it back
            currentQuestion = nextQuestionData.next_question;

            document.getElementById("question-number").innerText =
                nextQuestionData.current_question_number;

            // Clear answer and feedback
            document.getElementById("answer").value = "";
            document.getElementById("feedback").innerText = "";

            document.getElementById("next-btn").style.display = "none";

            nextQuestionData = null;
        });
    }
};