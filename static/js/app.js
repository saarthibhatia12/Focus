document.addEventListener('DOMContentLoaded', function () {
    // Elements for Clock and To-Do List
    const clockElement = document.getElementById('clock');
    const todoListElement = document.getElementById('todo-list');
    const todoInputElement = document.getElementById('todo-input');
    const addBtnElement = document.getElementById('add-btn');
    const awardVisual = document.getElementById('award-visual');

    // Elements for Pomodoro Timer
    const timerDisplay = document.getElementById('timer-display');
    const sessionInfo = document.getElementById('session-info');
    const startButton = document.getElementById('start-timer');
    const pauseButton = document.getElementById('pause-timer');
    const resetButton = document.getElementById('reset-timer');

    // Clock Functionality
    function updateClock() {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        clockElement.textContent = `${hours}:${minutes}`;
    }
    setInterval(updateClock, 1000);
    updateClock();

    // To-Do List Functionality
    function showAward() {
        if (awardVisual) {
            awardVisual.classList.remove('hidden');
            setTimeout(() => awardVisual.classList.add('hidden'), 1000);
        }
    }

    function addTodoItem() {
        const todoText = todoInputElement.value.trim();
        if (!todoText) {
            alert("Please enter a task.");
            return;
        }

        $.post('/add_task', { task: todoText }, function (data) {
            if (data.success) {
                const li = createTodoElement(todoText, todoListElement.children.length);
                todoListElement.appendChild(li);
                todoInputElement.value = '';
            } else {
                alert("Failed to add task. Please try again.");
            }
        }).fail(function () {
            alert("Error connecting to the server.");
        });
    }

    function createTodoElement(task, index) {
        const li = document.createElement('li');
        li.textContent = task;
        li.dataset.index = index;

        const toggleBtn = document.createElement('button');
        toggleBtn.textContent = 'Complete Task';
        toggleBtn.className = 'toggle-btn';
        toggleBtn.style.backgroundColor = 'black';
        toggleBtn.style.color = 'white';
        toggleBtn.style.borderRadius = '25px';

        li.appendChild(toggleBtn);
        return li;
    }

    function toggleTaskCompletion(e) {
        if (e.target.classList.contains('toggle-btn')) {
            const li = e.target.parentElement;
            const index = li.dataset.index;

            $.post('/toggle_task', { index: index }, function (data) {
                if (data.success) {
                    li.classList.toggle('completed');
                    if (li.classList.contains('completed')) {
                        showAward();
                    }
                } else {
                    alert("Failed to toggle task. Please try again.");
                }
            }).fail(function () {
                alert("Error connecting to the server.");
            });
        }
    }

    // Event Listeners for To-Do List
    addBtnElement.addEventListener('click', addTodoItem);
    todoInputElement.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addTodoItem();
        }
    });
    todoListElement.addEventListener('click', toggleTaskCompletion);

    // Pomodoro Timer Functionality
    let timerInterval;
    let isPaused = false;
    let currentSession = 'work'; // 'work', 'shortBreak', or 'longBreak'
    let sessionCount = 0; // Number of completed work sessions
    const durations = {
        work: 25 * 60, // 25 minutes
        shortBreak: 5 * 60, // 5 minutes
        longBreak: 15 * 60 // 15 minutes
    };
    let remainingTime = durations.work;

    function updateTimerDisplay() {
        const minutes = Math.floor(remainingTime / 60).toString().padStart(2, '0');
        const seconds = (remainingTime % 60).toString().padStart(2, '0');
        timerDisplay.textContent = `${minutes}:${seconds}`;
    }

    function startTimer() {
        if (isPaused) {
            isPaused = false;
            pauseButton.disabled = false;
            return;
        }

        startButton.disabled = true;
        pauseButton.disabled = false;

        timerInterval = setInterval(() => {
            if (remainingTime > 0) {
                remainingTime--;
                updateTimerDisplay();
            } else {
                clearInterval(timerInterval);
                handleSessionEnd();
            }
        }, 1000);
    }

    function pauseTimer() {
        isPaused = true;
        pauseButton.disabled = true;
        clearInterval(timerInterval);
    }

    function resetTimer() {
        clearInterval(timerInterval);
        isPaused = false;
        startButton.disabled = false;
        pauseButton.disabled = true;
        sessionCount = 0;
        currentSession = 'work';
        remainingTime = durations.work;
        updateTimerDisplay();
        sessionInfo.textContent = 'Work Session';
    }

    function handleSessionEnd() {
        if (currentSession === 'work') {
            sessionCount++;
            currentSession = sessionCount % 4 === 0 ? 'longBreak' : 'shortBreak';
        } else {
            currentSession = 'work';
        }

        remainingTime = durations[currentSession];
        sessionInfo.textContent =
            currentSession === 'work'
                ? 'Work Session'
                : currentSession === 'shortBreak'
                ? 'Short Break'
                : 'Long Break';

        startButton.disabled = false;
        pauseButton.disabled = true;
        updateTimerDisplay();
    }

    // Event Listeners for Pomodoro Timer
    startButton.addEventListener('click', startTimer);
    pauseButton.addEventListener('click', pauseTimer);
    resetButton.addEventListener('click', resetTimer);

    // Initialize Timer Display
    updateTimerDisplay();
});
