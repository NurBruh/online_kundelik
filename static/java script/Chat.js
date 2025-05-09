document.addEventListener('DOMContentLoaded', function() {
    const chatWidgetButton = document.getElementById('chatWidgetButton');
    const chatPopup = document.getElementById('chatPopup');
    const chatCloseBtn = document.getElementById('chatCloseBtn');
    const chatInput = document.getElementById('chatInput');
    const chatSendBtn = document.getElementById('chatSendBtn');
    const chatMessagesContainer = document.getElementById('chatMessages');

    // База знаний для ответов бота (ключевые слова и ответы)
    const knowledgeBase = [
        {
            keywords: ["smartoqulyq деген не", "что такое smartoqulyq", "платформа туралы", "о платформе", "платформа туралы айтып бере аласын ба?", "бул кандай сайт", "бұл қандай сайт"],
            answer: "SmartOqulyq – бұл мектеп оқушыларына, ата-аналарға және мұғалімдерге арналған инновациялық білім беру платформасы. Ол оқу үдерісін жеңілдетуге, үлгерімді бақылауға және білім беру материалдарына оңай қол жеткізуге көмектеседі."
        },
        {
            keywords: ["қалай қолданамын", "как пользоваться", "пайдалану", "инструкция", "сайтты калай колдануга болады"],
            answer: "Платформаны пайдалану үшін тіркелуіңіз немесе жүйеге кіруіңіз қажет. Оқушылар сабақ кестесін, бағаларын көре алады, тесттер тапсыра алады. Ата-аналар балаларының үлгерімін бақылай алады. Мұғалімдер электронды журнал жүргізіп, тапсырмалар бере алады. Толығырақ \"Біз туралы\" немесе \"Ұсыныстар\" бөлімдерінен оқи аласыз."
        },
        {
            keywords: ["мүмкіндіктер", "функции", "что можно делать", "сервисы", "не истеуге болады", "не істеуге болады"],
            answer: "Оқушылар үшін: электронды күнделік, сабақ кестесі, онлайн сабақтар мен тесттер, БЖБ/ТЖБ тапсыру, ҰБТ-ға дайындық. Ата-аналар үшін: баланың үлгерімін бақылау, үй тапсырмалары. Мұғалімдер үшін: электронды журнал, сандық білім беру қызметтері, дайын сабақтар."
        },
        {
            keywords: ["тіркелу", "регистрация", "как зарегистрироваться", "зарегистрироваться", "калай тиркелемин", "қалай тіркелемін"],
            answer: "Тіркелу үшін басты беттегі \"Бастау\" немесе \"Кіру\" батырмасын басып, әрі қарай нұсқауларды орындаңыз. Сізге рөліңізді (оқушы, ата-ана, мұғалім) таңдап, қажетті мәліметтерді енгізу керек болады."
        },
        {
            keywords: ["сәлем", "привет", "hello", "hi", "салем", "салам", "сәлеметсіз бе"],
            answer: "Сәлеметсіз бе! Мен SmartOqulyq көмекшісімін. Сізге қалай көмектесе аламын?"
        },
        {
            keywords: ["бағалар", "оценки", "бағаларымды қалай көремін", "где посмотреть оценки"],
            answer: "Оқушылар өз бағаларын жеке кабинеттеріндегі \"Электронды күнделік\" немесе \"Бағалар\" бөлімінен көре алады. Ата-аналар да балаларының бағаларын осы бөлімдер арқылы бақылай алады."
        },
        {
            keywords: ["сабақ кестесі", "расписание", "кесте", "сабак кестеси"],
            answer: "Сабақ кестесін жеке кабинетіңіздегі тиісті бөлімнен таба аласыз. Кестеде пәндер, уақыттары және мұғалімдер көрсетіледі."
        },
        {
            keywords: ["үй тапсырмасы", "домашнее задание", "дз", "уй жумысы", "үй жұмысы"],
            answer: "Үй тапсырмалары әдетте күнделікте немесе арнайы \"Тапсырмалар\" бөлімінде көрсетіледі. Мұғалімдер тапсырмаларды сол жерге жүктейді."
        },
        {
            keywords: ["тест", "тесттер", "тесты", "тест тапсыру", "сдать тест"],
            answer: "Онлайн тесттерді \"Тесттер\" немесе \"Бақылау жұмыстары\" бөлімінен тауып, тапсыра аласыз. Нәтижелеріңіз автоматты түрде сақталады."
        },
        {
            keywords: ["ұбт", "ент", "ҰБТ-ға дайындық", "подготовка к ЕНТ"],
            answer: "Платформада ҰБТ-ға дайындыққа арналған материалдар, сынақ тесттері және курстар болуы мүмкін. \"Ұсыныстар\" немесе арнайы \"ҰБТ дайындық\" бөлімін қараңыз."
        },
        {
            keywords: ["көмек", "помощь", "маған көмек керек", "мне нужна помощь", "сурак", "сұрақ"],
            answer: "Әрине, сұрағыңызды қойыңыз, мен сізге көмектесуге тырысамын! Егер нақты мәселе туындаса, сайттың \"Байланыс\" бөлімі арқылы техникалық қолдау қызметіне хабарласа аласыз."
        },
        {
            keywords: ["рахмет", "спасибо", "благодарю"],
            answer: "Оқасы жоқ! Басқа сұрақтарыңыз болса, хабарласыңыз."
        }
        // Сюда можно добавлять больше правил
    ];

    const defaultAnswer = "Кешіріңіз, мен бұл сұрақты түсінбедім. Басқаша сұрап көріңіз немесе толығырақ ақпарат алу үшін сайттың тиісті бөлімдерін қараңыз.";

    if (chatWidgetButton && chatPopup && chatCloseBtn && chatInput && chatSendBtn && chatMessagesContainer) {
        chatWidgetButton.addEventListener('click', function() {
            if (chatPopup.style.display === 'none' || chatPopup.style.display === '') {
                chatPopup.style.display = 'flex';
                chatWidgetButton.innerHTML = '<i class="fas fa-times"></i>';
            } else {
                chatPopup.style.display = 'none';
                chatWidgetButton.innerHTML = '<i class="fas fa-comments"></i>';
            }
        });

        chatCloseBtn.addEventListener('click', function() {
            chatPopup.style.display = 'none';
            chatWidgetButton.innerHTML = '<i class="fas fa-comments"></i>';
        });

        function addMessageToChat(message, sender) {
            const messageDiv = document.createElement('div');
            messageDiv.classList.add('chat-message', sender);
            messageDiv.textContent = message;
            chatMessagesContainer.appendChild(messageDiv);
            chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
        }

        function getBotResponse(userMessage) {
            const lowerUserMessage = userMessage.toLowerCase().trim(); // .trim() для удаления пробелов по краям
            for (const item of knowledgeBase) {
                for (const keyword of item.keywords) {
                    // Для более точного совпадения, можно проверять не только includes,
                    // но и полное совпадение или совпадение отдельных слов
                    if (lowerUserMessage.includes(keyword.toLowerCase())) {
                        return item.answer;
                    }
                }
            }
            return defaultAnswer;
        }

        function sendMessage() {
            const userMessage = chatInput.value.trim();
            if (userMessage) {
                addMessageToChat(userMessage, 'user');
                chatInput.value = '';

                // Имитация "загрузки" или "обдумывания" ботом
                const thinkingMessageDiv = document.createElement('div');
                thinkingMessageDiv.classList.add('chat-message', 'bot', 'thinking'); // Добавим класс 'thinking' для возможной стилизации
                thinkingMessageDiv.innerHTML = 'Ойлануда... <i class="fas fa-spinner fa-spin"></i>'; // Можете добавить иконку загрузки
                chatMessagesContainer.appendChild(thinkingMessageDiv);
                chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;


                // Получаем ответ от "бота"
                const botResponse = getBotResponse(userMessage);

                // Задержка перед ответом бота - 2 секунды
                setTimeout(function() {
                    // Удаляем сообщение "Ойлануда..."
                    const thinkingMsg = chatMessagesContainer.querySelector('.thinking');
                    if(thinkingMsg) {
                        chatMessagesContainer.removeChild(thinkingMsg);
                    }
                    // Показываем реальный ответ
                    addMessageToChat(botResponse, 'bot');
                }, 2000); // Задержка в 2000 миллисекунд (2 секунды)
            }
        }

        chatSendBtn.addEventListener('click', sendMessage);

        chatInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                sendMessage();
                event.preventDefault();
            }
        });

        // Добавляем первое приветственное сообщение от бота при открытии чата, если его еще нет
        // (можно сделать эту логику сложнее, чтобы оно не появлялось каждый раз при открытии,
        // а только при первой загрузке страницы, но для простоты пока так)
        if (chatMessagesContainer.children.length <= 1) { // Проверяем, есть ли там только первоначальное сообщение
             // Убрал автоматическое добавление сообщения при загрузке, так как оно уже есть в HTML
            // addMessageToChat("Сәлеметсіз бе! Мен SmartOqulyq көмекшісімін. Сізге қалай көмектесе аламын?", "bot");
        }


    } else {
        console.warn("Элементы чат-бота не найдены на странице. Убедитесь, что HTML-разметка присутствует и ID корректны.");
    }
});