```javascript
/* =========================================
   MTR TEAM MINI APP
   ========================================= */


/* TELEGRAM */

const tg = window.Telegram?.WebApp;

if (tg) {
    tg.ready();
    tg.expand();
}


/* HELPERS */

const $ = (selector) => {
    return document.querySelector(selector);
};


/* TELEGRAM USER */

let telegramUser = null;

try {
    telegramUser =
        tg?.initDataUnsafe?.user || null;
} catch (error) {
    telegramUser = null;
}


/*
    Если Mini App открыт не через Telegram,
    можно передать ?user_id=123
*/

const urlParams =
    new URLSearchParams(
        window.location.search
    );


const userId =
    telegramUser?.id ||
    urlParams.get("user_id") ||
    "demo";


/* =========================================
   CONFIG
   ========================================= */


/*
    ВАЖНО!

    Здесь укажи username своего бота
    БЕЗ символа @.
*/

const BOT_USERNAME = "@Mtreferall_bot";


/*
    Здесь укажи username поддержки.
*/

const SUPPORT_USERNAME = "@jogas_wor";


/* =========================================
   REFERRAL LINK
   ========================================= */

const referralLink =
    `https://t.me/${BOT_USERNAME}?start=ref_${userId}`;


$("#referralLink").textContent =
    referralLink;


/* =========================================
   DEMO DATA
   ========================================= */


/*
    Это временные данные.

    Позже они будут приходить
    с backend/API.
*/

const defaultStats = {

    refs: 3,

    bonus: 150,

    level: 1

};


let stats;


try {

    stats =
        JSON.parse(
            localStorage.getItem(
                "mtr_stats"
            )
        );

} catch {

    stats = null;

}


if (!stats) {

    stats = {
        ...defaultStats
    };

}


/* =========================================
   LEVEL SYSTEM
   ========================================= */

const levels = [

    {
        level: 1,
        name: "START",
        target: 10
    },

    {
        level: 2,
        name: "GROWTH",
        target: 25
    },

    {
        level: 3,
        name: "PRO",
        target: 50
    },

    {
        level: 4,
        name: "ELITE",
        target: 100
    }

];


function updateStats() {

    $("#refsValue").textContent =
        stats.refs;


    $("#bonusValue").textContent =
        stats.bonus;


    const currentLevel =
        levels[
            Math.min(
                stats.level - 1,
                levels.length - 1
            )
        ];


    const previousTarget =
        stats.level <= 1
            ? 0
            : levels[
                Math.min(
                    stats.level - 2,
                    levels.length - 1
                )
            ].target;


    const target =
        currentLevel.target;


    let progress =
        (
            (stats.refs - previousTarget)
            /
            (target - previousTarget)
        ) * 100;


    progress =
        Math.max(
            0,
            Math.min(
                100,
                progress
            )
        );


    $("#progressBar").style.width =
        `${progress}%`;


    $("#levelProgressText").textContent =
        `${stats.refs} / ${target}`;


    $("#levelNumber").textContent =
        String(stats.level)
            .padStart(2, "0");


    $("#levelName").textContent =
        currentLevel.name;

}


updateStats();


/* =========================================
   TOAST
   ========================================= */

function showToast(message) {

    const toast =
        $("#toast");


    toast.textContent =
        message;


    toast.classList.add(
        "show"
    );


    setTimeout(() => {

        toast.classList.remove(
            "show"
        );

    }, 1800);

}


/* =========================================
   COPY REFERRAL
   ========================================= */

async function copyReferral() {

    try {

        await navigator
            .clipboard
            .writeText(
                referralLink
            );


        showToast(
            "Ссылка скопирована"
        );


    } catch {

        showToast(
            "Не удалось скопировать"
        );

    }

}


$("#copyButton").onclick =
    copyReferral;


/* =========================================
   TELEGRAM SHARE
   ========================================= */

function shareReferral() {

    const text =
        encodeURIComponent(
            "Присоединяйся к MTR TEAM 👇"
        );


    const url =
        encodeURIComponent(
            referralLink
        );


    const shareUrl =
        `https://t.me/share/url?url=${url}&text=${text}`;


    if (
        tg &&
        typeof tg.openTelegramLink === "function"
    ) {

        tg.openTelegramLink(
            shareUrl
        );

    } else {

        window.open(
            shareUrl,
            "_blank"
        );

    }

}


$("#shareButton").onclick =
    shareReferral;


$("#inviteButton").onclick =
    shareReferral;


/* =========================================
   MODAL
   ========================================= */

const modal =
    $("#modal");


const modalContent =
    $("#modalContent");


function openModal(html) {

    modalContent.innerHTML =
        html;

    modal.classList.add(
        "show"
    );

}


function closeModal() {

    modal.classList.remove(
        "show"
    );

}


$("#modalClose").onclick =
    closeModal;


modal.onclick = (event) => {

    if (
        event.target === modal
    ) {

        closeModal();

    }

};


/* =========================================
   PROFILE
   ========================================= */

$("#profileButton").onclick =
    () => {

        const firstName =
            telegramUser?.first_name ||
            "Пользователь";


        const username =
            telegramUser?.username
                ? `@${telegramUser.username}`
                : "не указан";


        openModal(`

            <h2>Профиль</h2>

            <p>
                <b>
                    ${firstName}
                </b>
            </p>

            <p>
                Username:
                ${username}
            </p>

            <p>
                Telegram ID:
                ${userId}
            </p>

            <p>
                Рефералов:
                <b>${stats.refs}</b>
            </p>

            <p>
                Бонусов:
                <b>${stats.bonus}</b>
            </p>

        `);

    };


/* =========================================
   RULES
   ========================================= */

$("#rulesButton").onclick =
    () => {

        openModal(`

            <h2>
                Как это работает
            </h2>

            <ol>

                <li>
                    Скопируй свою
                    реферальную ссылку.
                </li>

                <li>
                    Отправь её друзьям
                    или поделись через Telegram.
                </li>

                <li>
                    Следи за количеством
                    приглашённых участников.
                </li>

                <li>
                    Достигай новых
                    уровней команды.
                </li>

            </ol>

        `);

    };


/* =========================================
   SUPPORT
   ========================================= */

$("#supportButton").onclick =
    () => {

        const url =
            `https://t.me/${SUPPORT_USERNAME}`;


        if (
            tg &&
            typeof tg.openTelegramLink === "function"
        ) {

            tg.openTelegramLink(
                url
            );

        } else {

            window.open(
                url,
                "_blank"
            );

        }

    };


/* =========================================
   THEME
   ========================================= */

const savedTheme =
    localStorage.getItem(
        "mtr_theme"
    );


if (
    savedTheme === "light"
) {

    document.body.classList.add(
        "light"
    );

}


$("#themeButton").onclick =
    () => {

        document.body.classList.toggle(
            "light"
        );


        const theme =
            document.body.classList.contains(
                "light"
            )
                ? "light"
                : "dark";


        localStorage.setItem(
            "mtr_theme",
            theme
        );

    };


/* =========================================
   DEMO API PLACE
   ========================================= */


/*
    В БУДУЩЕМ сюда можно подключить
    твой настоящий backend.

    Например:

    async function loadStats() {

        const response =
            await fetch(
                "https://api.example.com/user",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        initData:
                            tg.initData
                    })
                }
            );


        const data =
            await response.json();


        stats = data;

        updateStats();
    }

*/


console.log(
    "MTR TEAM Mini App loaded",
    {
        userId,
        referralLink
    }
);
```
