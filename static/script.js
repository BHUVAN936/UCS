"use strict";

document.addEventListener("DOMContentLoaded", function () {

    // =========================================================
    // THEME TOGGLE
    // =========================================================

    const themeToggle =
        document.getElementById("themeToggle");

    const root =
        document.documentElement;


    function updateThemeButton() {

        if (!themeToggle) {
            return;
        }

        const dark =
            root.getAttribute("data-theme") === "dark";

        const icon =
            themeToggle.querySelector("i");


        if (icon) {

            icon.className =
                dark
                    ? "fa-solid fa-sun"
                    : "fa-solid fa-moon";

        }


        themeToggle.setAttribute(
            "aria-label",
            dark
                ? "Switch to light mode"
                : "Switch to dark mode"
        );


        themeToggle.setAttribute(
            "title",
            dark
                ? "Switch to light mode"
                : "Switch to dark mode"
        );

    }


    function setTheme(theme) {

        root.setAttribute(
            "data-theme",
            theme
        );


        document.body.classList.toggle(
            "dark-theme",
            theme === "dark"
        );


        try {

            localStorage.setItem(
                "uce-theme",
                theme
            );

        }
        catch (error) {

            console.warn(
                "Unable to save theme.",
                error
            );

        }


        updateThemeButton();

    }


    let savedTheme = "light";

    try {

        const storedTheme =
            localStorage.getItem("uce-theme");

        if (
            storedTheme === "dark" ||
            storedTheme === "light"
        ) {

            savedTheme =
                storedTheme;

        }

    }
    catch (error) {

        savedTheme = "light";

    }


    setTheme(savedTheme);


    if (themeToggle) {

        themeToggle.addEventListener(
            "click",
            function (event) {

                event.preventDefault();

                const currentTheme =
                    root.getAttribute("data-theme");


                setTheme(
                    currentTheme === "dark"
                        ? "light"
                        : "dark"
                );

            }
        );

    }


    // =========================================================
    // MOBILE NAVIGATION
    // =========================================================

    const mobileButton =
        document.getElementById(
            "mobileMenuButton"
        );

    const navigation =
        document.getElementById(
            "mainNavigation"
        );


    if (
        mobileButton &&
        navigation
    ) {

        mobileButton.addEventListener(
            "click",
            function () {

                const open =
                    navigation.classList.toggle(
                        "mobile-open"
                    );


                mobileButton.setAttribute(
                    "aria-expanded",
                    String(open)
                );


                const icon =
                    mobileButton.querySelector("i");


                if (icon) {

                    icon.className =
                        open
                            ? "fa-solid fa-xmark"
                            : "fa-solid fa-bars";

                }

            }
        );


        navigation
            .querySelectorAll("a")
            .forEach(
                function (link) {

                    link.addEventListener(
                        "click",
                        function () {

                            navigation.classList.remove(
                                "mobile-open"
                            );


                            mobileButton.setAttribute(
                                "aria-expanded",
                                "false"
                            );


                            const icon =
                                mobileButton.querySelector("i");


                            if (icon) {

                                icon.className =
                                    "fa-solid fa-bars";

                            }

                        }
                    );

                }
            );

    }


    // =========================================================
    // MODULE ACCORDIONS
    // =========================================================

    const modules =
        document.querySelectorAll(
            ".portal-module"
        );


    modules.forEach(
        function (module) {

            const header =
                module.querySelector(
                    "[data-module-toggle]"
                );

            const body =
                module.querySelector(
                    ".module-body"
                );


            if (
                !header ||
                !body
            ) {

                return;

            }


            /*
             * Set initial arrow according
             * to the existing HTML state.
             */
            const initiallyOpen =
                header.getAttribute(
                    "aria-expanded"
                ) === "true";


            if (initiallyOpen) {

                module.classList.add(
                    "active"
                );

                module.classList.add(
                    "open"
                );

                body.hidden =
                    false;

            }
            else {

                body.hidden =
                    true;

            }


            updateModuleArrow(
                module,
                initiallyOpen
            );


            header.addEventListener(
                "click",
                function (event) {

                    event.preventDefault();

                    event.stopPropagation();


                    const isCurrentlyOpen =
                        header.getAttribute(
                            "aria-expanded"
                        ) === "true";


                    const willOpen =
                        !isCurrentlyOpen;


                    /*
                     * Close every other module.
                     */
                    modules.forEach(
                        function (other) {

                            if (
                                other === module
                            ) {

                                return;

                            }


                            const otherHeader =
                                other.querySelector(
                                    "[data-module-toggle]"
                                );

                            const otherBody =
                                other.querySelector(
                                    ".module-body"
                                );


                            if (otherHeader) {

                                otherHeader.setAttribute(
                                    "aria-expanded",
                                    "false"
                                );

                            }


                            if (otherBody) {

                                otherBody.hidden =
                                    true;

                            }


                            other.classList.remove(
                                "active"
                            );

                            other.classList.remove(
                                "open"
                            );


                            updateModuleArrow(
                                other,
                                false
                            );

                        }
                    );


                    /*
                     * Open/close selected module.
                     */
                    header.setAttribute(
                        "aria-expanded",
                        String(willOpen)
                    );


                    body.hidden =
                        !willOpen;


                    module.classList.toggle(
                        "active",
                        willOpen
                    );


                    module.classList.toggle(
                        "open",
                        willOpen
                    );


                    updateModuleArrow(
                        module,
                        willOpen
                    );

                }
            );

        }
    );


    // =========================================================
    // CATEGORY CARDS
    // =========================================================

    document
        .querySelectorAll(
            ".subtopic-card"
        )
        .forEach(
            function (button) {

                button.addEventListener(
                    "click",
                    async function (event) {

                        /*
                         * Prevent category click from
                         * triggering the module header.
                         */
                        event.preventDefault();

                        event.stopPropagation();


                        const module =
                            button.closest(
                                ".portal-module"
                            );


                        if (!module) {

                            return;

                        }


                        /*
                         * Mark selected category.
                         */
                        module
                            .querySelectorAll(
                                ".subtopic-card"
                            )
                            .forEach(
                                function (item) {

                                    item.classList.remove(
                                        "active"
                                    );

                                }
                            );


                        button.classList.add(
                            "active"
                        );


                        const moduleKey =
                            button.dataset.module ||
                            module.dataset.module;


                        const topic =
                            button.dataset.topic;


                        const content =
                            module.querySelector(
                                ".information-panel"
                            );


                        if (
                            !moduleKey ||
                            !topic ||
                            !content
                        ) {

                            return;

                        }


                        await loadTopic(
                            moduleKey,
                            topic,
                            content
                        );

                    }
                );

            }
        );


    // =========================================================
    // MODULE SEARCH
    // =========================================================

    const searchInput =
        document.getElementById(
            "moduleSearch"
        );

    const noResults =
        document.getElementById(
            "noModuleResults"
        );


    if (searchInput) {

        searchInput.addEventListener(
            "input",
            function () {

                const query =
                    searchInput.value
                        .trim()
                        .toLowerCase();


                let visibleCount =
                    0;


                modules.forEach(
                    function (module) {

                        const searchableText =
                            (
                                module.dataset.search ||
                                module.innerText ||
                                ""
                            )
                            .toLowerCase();


                        const matches =
                            !query ||
                            searchableText.includes(
                                query
                            );


                        module.style.display =
                            matches
                                ? ""
                                : "none";


                        if (matches) {

                            visibleCount++;

                        }

                    }
                );


                if (noResults) {

                    noResults.hidden =
                        visibleCount !== 0;

                }

            }
        );

    }


    // =========================================================
    // UPDATES NAVIGATION
    // =========================================================

    document
        .querySelectorAll(
            'a[href$="#updates"], a[href*="#updates"]'
        )
        .forEach(
            function (link) {

                link.addEventListener(
                    "click",
                    function (event) {

                        const section =
                            document.getElementById(
                                "updates"
                            );


                        /*
                         * If an Updates section exists
                         * on the current page, scroll to it.
                         */
                        if (section) {

                            event.preventDefault();


                            section.scrollIntoView(
                                {
                                    behavior:
                                        "smooth",

                                    block:
                                        "start"
                                }
                            );


                            /*
                             * Keep URL hash.
                             */
                            try {

                                history.pushState(
                                    null,
                                    "",
                                    "#updates"
                                );

                            }
                            catch (error) {

                                // Ignore history errors.

                            }

                        }

                    }
                );

            }
        );


    /*
     * If page opened directly with #updates,
     * scroll to the Updates section.
     */
    if (
        window.location.hash ===
        "#updates"
    ) {

        const updates =
            document.getElementById(
                "updates"
            );


        if (updates) {

            setTimeout(
                function () {

                    updates.scrollIntoView(
                        {
                            behavior:
                                "smooth",

                            block:
                                "start"
                        }
                    );

                },
                100
            );

        }

    }


    // =========================================================
    // FLASH MESSAGES
    // =========================================================

    setupFlashMessages();

});


// =============================================================
// MODULE ARROW
// =============================================================

function updateModuleArrow(
    module,
    open
) {

    if (!module) {

        return;

    }


    const arrow =
        module.querySelector(
            ".module-toggle i"
        );


    if (!arrow) {

        return;

    }


    arrow.className =
        open
            ? "fa-solid fa-chevron-up"
            : "fa-solid fa-chevron-down";


    /*
     * Gives the opened arrow the
     * same accent color used by
     * your portal.
     */
    if (open) {

        arrow.style.color =
            "var(--accent, #19c6c8)";

    }
    else {

        arrow.style.color =
            "";

    }

}


// =============================================================
// LOAD DATA FOR HOMEPAGE CATEGORY
// =============================================================

async function loadTopic(
    moduleKey,
    topic,
    content
) {

    content.classList.add(
        "visible"
    );


    content.innerHTML = `
        <div class="loading-data">

            <i class="fa-solid fa-spinner fa-spin"></i>

            <p>
                Loading information...
            </p>

        </div>
    `;


    try {

        const url =
            "/api/data/" +
            encodeURIComponent(
                moduleKey
            ) +
            "/" +
            encodeURIComponent(
                topic
            );


        const response =
            await fetch(
                url,
                {
                    method: "GET",

                    headers: {
                        "Accept":
                            "application/json"
                    },

                    cache:
                        "no-store"
                }
            );


        let result =
            null;


        try {

            result =
                await response.json();

        }
        catch (error) {

            throw new Error(
                "The server returned an invalid response."
            );

        }


        if (
            !response.ok ||
            !result.success
        ) {

            throw new Error(
                result.error ||
                `Unable to load data (${response.status}).`
            );

        }


        content.innerHTML =
            buildDataView(
                result
            );

    }
    catch (error) {

        console.error(
            "UCE Connect data loading error:",
            error
        );


        content.innerHTML = `
            <div class="no-data">

                <i class="fa-solid fa-triangle-exclamation"></i>

                <h3>
                    Unable to load data
                </h3>

                <p>
                    ${escapeHtml(
                        error.message
                    )}
                </p>

            </div>
        `;

    }

}


// =============================================================
// BUILD HOMEPAGE DATA VIEW
// =============================================================

function buildDataView(
    result
) {

    const rows =
        Array.isArray(result.data)
            ? result.data
            : [];


    const analysis =
        result.analysis || {};


    if (
        rows.length === 0
    ) {

        return `
            <div class="no-data">

                <i class="fa-solid fa-folder-open"></i>

                <h3>
                    No data uploaded yet
                </h3>

                <p>
                    No records are currently available for this category.
                </p>

            </div>
        `;

    }


    /*
     * Get every column from the
     * returned records.
     */
    const columns =
        [];


    rows.forEach(
        function (row) {

            if (
                !row ||
                typeof row !== "object"
            ) {

                return;

            }


            Object.keys(row)
                .forEach(
                    function (column) {

                        if (
                            !columns.includes(
                                column
                            )
                        ) {

                            columns.push(
                                column
                            );

                        }

                    }
                );

        }
    );


    let html = `
        <div class="data-summary">

            <div>
                <strong>
                    ${escapeHtml(
                        analysis.rows ??
                        rows.length
                    )}
                </strong>

                <span>
                    Rows
                </span>
            </div>


            <div>
                <strong>
                    ${escapeHtml(
                        analysis.columns ??
                        columns.length
                    )}
                </strong>

                <span>
                    Columns
                </span>
            </div>


            <div>
                <strong>
                    ${escapeHtml(
                        result.module ||
                        ""
                    )}
                </strong>

                <span>
                    Module
                </span>
            </div>


            <div>
                <strong>
                    ${escapeHtml(
                        result.title ||
                        ""
                    )}
                </strong>

                <span>
                    Category
                </span>
            </div>

        </div>


        <div class="data-table-wrapper">

            <table class="data-table">

                <thead>

                    <tr>
    `;


    columns.forEach(
        function (column) {

            html += `
                <th>
                    ${escapeHtml(
                        column
                    )}
                </th>
            `;

        }
    );


    html += `
                    </tr>

                </thead>

                <tbody>
    `;


    rows.forEach(
        function (row) {

            html += "<tr>";


            columns.forEach(
                function (column) {

                    html += `
                        <td>
                            ${escapeHtml(
                                row[column] ??
                                ""
                            )}
                        </td>
                    `;

                }
            );


            html += "</tr>";

        }
    );


    html += `
                </tbody>

            </table>

        </div>
    `;


    return html;

}


// =============================================================
// FLASH MESSAGES
// =============================================================

function setupFlashMessages() {

    const messages =
        document.querySelectorAll(
            ".flash"
        );


    messages.forEach(
        function (message) {

            /*
             * Existing close button.
             */
            const closeButton =
                message.querySelector(
                    ".flash-close"
                );


            if (closeButton) {

                closeButton.addEventListener(
                    "click",
                    function (event) {

                        event.preventDefault();

                        removeFlash(
                            message
                        );

                    }
                );

            }


            /*
             * Automatically disappear
             * after exactly 2 seconds.
             */
            window.setTimeout(
                function () {

                    removeFlash(
                        message
                    );

                },
                2000
            );

        }
    );

}


// =============================================================
// REMOVE FLASH MESSAGE
// =============================================================

function removeFlash(
    message
) {

    if (
        !message ||
        !message.parentElement
    ) {

        return;

    }


    message.style.transition =
        "opacity 0.2s ease, transform 0.2s ease";


    message.style.opacity =
        "0";


    message.style.transform =
        "translateY(-5px)";


    window.setTimeout(
        function () {

            if (
                message &&
                message.parentElement
            ) {

                message.parentElement.removeChild(
                    message
                );

            }

        },
        200
    );

}


// =============================================================
// HTML ESCAPE
// =============================================================

function escapeHtml(
    value
) {

    return String(
        value ?? ""
    )
    .replace(
        /&/g,
        "&amp;"
    )
    .replace(
        /</g,
        "&lt;"
    )
    .replace(
        />/g,
        "&gt;"
    )
    .replace(
        /"/g,
        "&quot;"
    )
    .replace(
        /'/g,
        "&#039;"
    );

}