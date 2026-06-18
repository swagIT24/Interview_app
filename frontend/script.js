let sessionId = null;
let nextQuestionData = null;
let currentQuestion = null;
/* ================= LOGIN ================= */

let currentAudio;
let currentAudioB64 = null;
let questionCount = 1;

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
        const meResponse = await fetch("/me", { credentials: "include" });
        const user = await meResponse.json();
        if (user.onboarding_completed === 0) {
            window.location.href = "/onboarding";
        } else if (!data.profile_completed) {
            window.location.href = "/goal-setting";
        } else {
            window.location.href = "/dashboard";
        }

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
    sessionStorage.setItem("current_audio", data.audio);
    currentQuestion = data.current_question;

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

    const feedbackEl = document.getElementById("feedback");
    feedbackEl.innerText = "Evaluating...";

    console.time("submit-answer");

    let response = await fetch("/submit-answer", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
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
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                refresh_token: localStorage.getItem("refresh_token")
            })
        });

        if (refreshResponse.ok) {

            console.log("Token refreshed, retrying submit...");

            response = await fetch("/submit-answer", {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
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

    console.timeEnd("submit-answer");

    // ← CHANGED: format feedback with sections
    feedbackEl.innerHTML = "<b>Score: " + data.score + " / 15</b><br><br>" +
        data.feedback
            .replace(/Strengths:/g, "<b>Strengths:</b>")
            .replace(/Weaknesses:/g, "<br><br><b>Weaknesses:</b>")
            .replace(/Tip:/g, "<br><br><b>Tip:</b>")
            .replace(/Example:/g, "<br><br><b>Example:</b>");

    console.log("NEXT QUESTION:", data.next_question);

    if (data.next_question) {
        nextQuestionData = data;
        document.getElementById("next-btn").style.display = "inline-block";

    } else if (data.is_completed) {
        document.getElementById("question").innerText = "Interview Completed!";
    }

    nextQuestionData = nextQuestionData || {};
}
/* ================= REGISTER ================= */

let _registerStep = 1;
let _registerData = {};

async function register() {
    const msg = document.getElementById("register-message");
    msg.classList.remove("success");

    if (_registerStep === 1) {
        const name = document.getElementById("register-name").value.trim();
        const email = document.getElementById("register-email").value.trim();
        const password = document.getElementById("register-password").value;

        if (!name || !email || !password) {
            msg.innerText = "Please fill in all fields.";
            return;
        }

        const response = await fetch("/register-request-otp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, password })
        });

        const data = await response.json();

        if (response.ok) {
            _registerData = { name, email, password };
            _registerStep = 2;

            document.getElementById("otp-field").style.display = "block";
            document.getElementById("register-name").disabled = true;
            document.getElementById("register-email").disabled = true;
            document.getElementById("register-password").disabled = true;
            document.getElementById("register-btn").innerText = "Verify & Create Account";

            msg.classList.add("success");
            msg.innerText = "OTP sent to your email. Check your inbox.";
        } else {
            msg.innerText = data.detail || "Failed to send OTP.";
        }

    } else {
        const otp = document.getElementById("register-otp").value.trim();

        if (!otp) {
            msg.innerText = "Please enter the OTP.";
            return;
        }

        const response = await fetch("/verify-otp-register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ..._registerData, otp })
        });

        const data = await response.json();

        if (response.ok) {
            msg.classList.add("success");
            msg.innerText = "Registered successfully!";
            setTimeout(() => { window.location.href = "/"; }, 1500);
        } else {
            msg.innerText = data.detail || "Registration failed.";
        }
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



async function preloadQuestionAudio(questionText) {
    const response = await fetch("/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: questionText })
    });
    const data = await response.json();
    currentAudioB64 = data.audio;
}

function playQuestionAudio() {
    if (!currentAudioB64) return;
    if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
    }
    currentAudio = new Audio("data:audio/mp3;base64," + currentAudioB64);
    currentAudio.play();
}


function uploadResume() {                        // define function
    const input = document.createElement("input"); // create a hidden file input
    input.type = "file";                          // make it a file picker
    input.accept = ".pdf";                        // only accept PDFs
    
    input.onchange = async function() {           // when user picks a file
        const file = input.files[0];              // get the selected file
        if (!file) return;                        // if no file, stop

        const formData = new FormData();          // create a container
        formData.append("file", file);            // put the file in it

        const response = await fetch("/upload-resume", {  // send to backend
            method: "POST",                       // POST request
            body: formData                        // attach the file
        });

        const data = await response.json();       // read backend response
        console.log("Resume upload response:", data); // print to console
        alert("Resume uploaded!");                // show popup to user
    };

    input.click();                                // programmatically click the file picker
}
/* ================= PAGE LOAD ================= */

window.onload = function () {

    if (window.location.pathname.includes("interview.html")) {

        const question = sessionStorage.getItem("current_question");

        if (question) {
            document.getElementById("question").innerText = question;
            currentQuestion = question;

            const btn = document.querySelector('[onclick="playQuestionAudio()"]');
            if (btn) btn.innerText = "⏳ Loading audio...";

            fetch("/tts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: question })
            })
            .then(res => res.json())
            .then(data => {
                currentAudioB64 = data.audio;
                if (btn) btn.innerText = "🔊 Read Question";
                console.log("First question audio ready");
            });
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

                        answerBox.value = data.transcript;

                        document.getElementById("feedback").innerHTML = 
                            "<b>Score: " + data.evaluation.score + " / 15</b><br><br>" +
                            data.evaluation.feedback
                                .replace(/Strengths:/g, "<b>Strengths:</b>")
                                .replace(/Weaknesses:/g, "<br><br><b>Weaknesses:</b>")
                                .replace(/Tip:/g, "<br><br><b>Tip:</b>")
                                .replace(/Example:/g, "<br><br><b>Example:</b>");
                        
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
            console.log("nextQuestionData:", nextQuestionData);
            currentAudioB64 = null; 
            document.getElementById("question").innerText =
                nextQuestionData.next_question;

            currentQuestion = nextQuestionData.next_question;
            currentAudioB64 = nextQuestionData.audio; 

            questionCount++;
            document.getElementById("question-number").innerText = questionCount;

            // Clear answer and feedback
            document.getElementById("answer").value = "";
            document.getElementById("feedback").innerText = "";

            document.getElementById("next-btn").style.display = "none";

            nextQuestionData = null;
        });
    }
};


