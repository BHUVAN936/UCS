"use strict";

/*
 * UCE Connect - shared browser behavior
 *
 * This file intentionally keeps the existing UI/CSS intact.
 * It only handles interaction and data loading.
 */

document.addEventListener("DOMContentLoaded", function () {

    // =========================================================
    // THEME
    // =========================================================

    const root = document.documentElement;
    const themeToggle = document.getElementById("themeToggle");

    function updateThemeButton() {
        if (!themeToggle) return;

        const isDark = root.getAttribute("data-theme") === "dark";
        const icon = themeToggle.querySelector("i");

        if (icon) {
            icon.className = isDark
                ? "fa-solid fa-sun"
                : "fa-solid fa-moon";
        }

        themeToggle.setAttribute(
            "aria-label",
            isDark ? "Switch to light mode" : "Switch to dark mode"
        );

        themeToggle.setAttribute(
            "title",
            isDark ? "Switch to light mode" : "Switch to dark mode"
        );
    }

    function setTheme(theme) {
        const value = theme === "dark" ? "dark" : "light";

        root.setAttribute("data-theme", value);
        document.body.setAttribute("data-theme", value);
        document.body.classList.toggle(
            "dark-theme",
            value === "dark"
        );

        try {
            localStorage.setItem(
                "uce-theme",
                value
            );
        } catch (error) {
            // Storage can be unavailable.
        }

        updateThemeButton();
    }

    let savedTheme = "light";

    try {
        const stored =
            localStorage.getItem("uce-theme");

        if (
            stored === "dark" ||
            stored === "light"
        ) {
            savedTheme = stored;
        }
    } catch (error) {
        savedTheme = "light";
    }

    setTheme(savedTheme);

    if (themeToggle) {

        themeToggle.addEventListener(
            "click",
            function (event) {

                event.preventDefault();

                const current =
                    root.getAttribute("data-theme");

                setTheme(
                    current === "dark"
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
    //
    // IMPORTANT:
    // Modules work in BOTH admin and user mode.
    //
    // Every module starts CLOSED after refresh.
    //
    // Click the arrow:
    //     ↓ = open
    //     ↑ = close
    //
    // Only one module is open at a time.
    // =========================================================

    const modules =
        Array.from(
            document.querySelectorAll(
                ".portal-module"
            )
        );


    const currentRole =
        document.body.getAttribute(
            "data-role"
        ) || "guest";


    const isAdmin =
        currentRole === "admin";


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

    }


    function setModuleState(
        module,
        open
    ) {

        if (!module) {
            return;
        }


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


        header.setAttribute(
            "aria-expanded",
            String(open)
        );


        body.hidden =
            !open;


        module.classList.toggle(
            "active",
            open
        );


        module.classList.toggle(
            "open",
            open
        );


        updateModuleArrow(
            module,
            open
        );

    }


    function closeOtherModules(
        selectedModule
    ) {

        modules.forEach(
            function (module) {

                if (
                    module !== selectedModule
                ) {

                    setModuleState(
                        module,
                        false
                    );

                }

            }
        );

    }


    // =========================================================
    // INITIALIZE ALL MODULES
    // =========================================================

    modules.forEach(
        function (
            module,
            index
        ) {

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
             * IMPORTANT:
             *
             * Every module starts CLOSED after
             * a page load or browser refresh.
             *
             * The user/admin must click the
             * arrow to explore the module.
             */

            setModuleState(
                module,
                false
            );


            // =================================================
            // MODULE CLICK
            // =================================================

            header.addEventListener(
                "click",
                function (event) {

                    event.preventDefault();

                    event.stopPropagation();


                    const currentlyOpen =
                        header.getAttribute(
                            "aria-expanded"
                        ) === "true";


                    const nextState =
                        !currentlyOpen;


                    /*
                     * If opening a module,
                     * close all other modules.
                     */

                    if (nextState) {

                        closeOtherModules(
                            module
                        );

                    }


                    /*
                     * Open or close selected module.
                     */

                    setModuleState(
                        module,
                        nextState
                    );

                }
            );


            // =================================================
            // ACCESSIBILITY
            // =================================================

            const titleElement =
                module.querySelector("h3");


            const title =
                titleElement
                    ? titleElement.textContent.trim()
                    : `module ${index + 1}`;


            header.setAttribute(
                "aria-label",
                header.getAttribute(
                    "aria-label"
                ) ||
                `Toggle ${title}`
            );

        }
    );


    // =========================================================
    // ADMIN SUBMODULE DATA CARDS
    // =========================================================
    //
    // User mode:
    //     Submodules are visible.
    //     Submodules do NOT open datasets.
    //
    // Admin mode:
    //     Submodules can load their data.
    // =========================================================

    document
        .querySelectorAll(
            ".subtopic-card"
        )
        .forEach(
            function (card) {

                /*
                 * User mode uses non-button cards.
                 * Only admin buttons are interactive.
                 */

                if (
                    card.tagName.toLowerCase() !==
                    "button"
                ) {

                    return;

                }


                card.addEventListener(
                    "click",
                    async function (event) {

                        event.preventDefault();

                        event.stopPropagation();


                        const module =
                            card.closest(
                                ".portal-module"
                            );


                        if (!module) {
                            return;
                        }


                        /*
                         * Remove active state
                         * from other submodules.
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


                        card.classList.add(
                            "active"
                        );


                        const moduleKey =
                            card.dataset.module ||
                            module.dataset.module;


                        const topic =
                            card.dataset.topic;


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

                            visibleCount += 1;

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
    // UPDATES HASH NAVIGATION
    // =========================================================

    document
        .querySelectorAll(
            'a[href*="#updates"]'
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


                        if (!section) {
                            return;
                        }


                        event.preventDefault();


                        section.scrollIntoView(
                            {
                                behavior:
                                    "smooth",

                                block:
                                    "start"
                            }
                        );


                        try {

                            history.pushState(
                                null,
                                "",
                                "#updates"
                            );

                        } catch (error) {

                            // Ignore history API restrictions.

                        }

                    }
                );

            }
        );


    // =========================================================
    // OPEN UPDATES WHEN URL HAS #updates
    // =========================================================

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
// ADMIN DATA LOADING
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
                    method:
                        "GET",

                    headers: {
                        "Accept":
                            "application/json"
                    },

                    cache:
                        "no-store"
                }
            );


        let result;


        try {

            result =
                await response.json();

        } catch (error) {

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

    } catch (error) {

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
// BUILD ADMIN DATA VIEW
// =============================================================

function buildDataView(
    result
) {

    const rows =
        Array.isArray(
            result.data
        )
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
// REMOVE FLASH
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