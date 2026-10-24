// Metadata editors (tags, categories): chips that each carry a hidden form input, and a text box with a dropdown
// of choices under it. Tags offer the tags already in use (from the server, most used first) and accept new
// ones; categories offer only the tree's leaves. One delegated set of listeners serves every editor on the page,
// including editors htmx swaps in later.
(function () {
    if (window.metaEditors) return;
    window.metaEditors = true;

    function chip(editor, value, text) {
        const span = document.createElement("span");
        span.className = "meta-chip";
        span.dataset.value = value;
        if (editor.dataset.ordered) span.title = "click to make this the primary category";
        const label = document.createElement("span");
        label.className = "meta-chip-label";
        label.textContent = text;
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = editor.dataset.kind;
        input.value = value;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "meta-remove text-dim hover:bg-paper hover:text-ink";
        remove.textContent = "[x]";
        span.append(label, input, remove);
        return span;
    }

    function chips(editor) {
        return editor.querySelector(".meta-chips");
    }

    function note(editor, text) {
        const n = editor.querySelector(".meta-note");
        if (n) n.textContent = text || "";
    }

    function values(editor) {
        return [...chips(editor).querySelectorAll(".meta-chip")].map(c => c.dataset.value);
    }

    // "3 of 10" under the box
    function count(editor) {
        const c = editor.querySelector(".meta-count");
        if (c && editor.dataset.max) c.textContent = `${values(editor).length} of ${editor.dataset.max}`;
    }

    function countAll(root) {
        root.querySelectorAll(".meta-editor[data-max]").forEach(count);
    }

    function add(editor, value, text) {
        const max = parseInt(editor.dataset.max || "0", 10);
        if (!value || values(editor).includes(value)) return;
        // Miscellaneous means "nowhere else": the server refuses it next to a real category
        const misc = editor.dataset.alone;
        if (misc && values(editor).length && (value === misc || values(editor).includes(misc))) {
            note(editor, "Miscellaneous cannot be combined with other categories");
            return;
        }
        if (max && values(editor).length >= max) {
            note(editor, `at most ${max}`);
            return;
        }
        chips(editor).append(chip(editor, value, text));
        chips(editor).scrollTop = chips(editor).scrollHeight; // the new one is in view
        note(editor, "");
        count(editor);
    }

    // tags: the typed text becomes a chip (a comma separates several)
    function addTyped(editor, input) {
        for (const raw of input.value.split(",")) {
            const tag = raw.trim().toLowerCase().replace(/\s+/g, "-");
            if (tag) add(editor, tag, tag);
        }
        input.value = "";
    }

    // --- the dropdown ------------------------------------------------------------------------------------------

    let timer; // the pending suggestion request

    function menu(editor) {
        return editor.querySelector(".meta-menu");
    }

    function close(editor) {
        clearTimeout(timer); // a suggestion request still on its way must not reopen it
        const m = menu(editor);
        m.hidden = true;
        m.innerHTML = "";
    }

    // choices: [{value, label, hint}]; the first is highlighted so Enter takes it
    function show(editor, choices) {
        const m = menu(editor);
        m.innerHTML = "";
        for (const choice of choices) {
            const li = document.createElement("li");
            li.className = "meta-option";
            li.dataset.value = choice.value;
            li.dataset.label = choice.label;
            li.textContent = choice.label;
            if (choice.hint) {
                const hint = document.createElement("span");
                hint.className = "text-dim";
                hint.textContent = " " + choice.hint;
                li.append(hint);
            }
            m.append(li);
        }
        m.hidden = choices.length === 0;
        place(editor);
        highlight(editor, 0);
    }

    // under the box, as wide as it, using all the room below it (or above, when there is more room there)
    function place(editor) {
        const m = menu(editor);
        if (m.hidden) return;
        const box = editor.querySelector(".meta-field").getBoundingClientRect();
        const below = window.innerHeight - box.bottom - 8;
        const above = box.top - 8;
        const up = below < 160 && above > below;
        m.style.left = `${box.left}px`;
        m.style.minWidth = `${box.width}px`;
        m.style.maxHeight = `${Math.max(80, up ? above : below)}px`; // all the room there is: it scrolls only if needed
        m.style.top = up ? "" : `${box.bottom}px`;
        m.style.bottom = up ? `${window.innerHeight - box.top}px` : "";
    }

    function options(editor) {
        return [...menu(editor).querySelectorAll(".meta-option")];
    }

    function highlight(editor, index) {
        const all = options(editor);
        all.forEach((o, i) => o.classList.toggle("meta-option-active", i === index));
        if (all[index]) all[index].scrollIntoView({block: "nearest"});
    }

    function active(editor) {
        return menu(editor).querySelector(".meta-option-active");
    }

    // a pick closes the menu (it would otherwise cover the editor below); typing or arrow keys reopen it
    function pick(editor, option) {
        add(editor, option.dataset.value, option.dataset.label);
        const input = editor.querySelector(".meta-input");
        input.value = "";
        close(editor);
        input.focus();
    }

    function refresh(editor, input) {
        const typed = input.value.trim().toLowerCase();
        const chosen = values(editor);
        const max = parseInt(editor.dataset.max || "0", 10);
        if (max && chosen.length >= max) {
            close(editor); // full: nothing more can be added
            return;
        }
        if (editor.dataset.free) {
            clearTimeout(timer);
            timer = setTimeout(async () => {
                const r = await fetch(editor.dataset.suggest + "?q=" + encodeURIComponent(typed));
                // stale: the box lost focus, or its text changed (or was turned into a chip) meanwhile
                if (!r.ok || document.activeElement !== input || input.value.trim().toLowerCase() !== typed) return;
                const tags = (await r.json()).filter(t => !chosen.includes(t.tag));
                show(editor, tags.map(t => ({value: t.tag, label: t.tag, hint: `· ${t.count}`})));
            }, 120);
        } else {
            const leaves = JSON.parse(editor.dataset.choices);
            show(editor, leaves
                .filter(([path, label]) => !chosen.includes(path) && label.toLowerCase().includes(typed))
                .map(([path, label]) => ({value: path, label})));
        }
    }

    // the category the typed text names: the leaf whose name ("Kitchen" in "Home › Kitchen") or whole label
    // it is, else the one leaf that contains it
    function onlyMatch(editor, input) {
        const typed = input.value.trim().toLowerCase();
        if (!typed) return null;
        const leaves = JSON.parse(editor.dataset.choices);
        const named = leaves.filter(([, label]) =>
            label.toLowerCase() === typed || label.split("›").pop().trim().toLowerCase() === typed);
        const found = named.length === 1 ? named : leaves.filter(([, label]) => label.toLowerCase().includes(typed));
        return found.length === 1 ? {dataset: {value: found[0][0], label: found[0][1]}} : null;
    }

    document.addEventListener("focusin", e => {
        const input = e.target.closest(".meta-input");
        if (input) refresh(input.closest(".meta-editor"), input);
    });

    document.addEventListener("focusout", e => {
        const input = e.target.closest(".meta-input");
        if (!input) return;
        const editor = input.closest(".meta-editor");
        setTimeout(() => { if (document.activeElement !== input) close(editor); }, 150);
    });

    document.addEventListener("input", e => {
        const input = e.target.closest(".meta-input");
        if (!input) return;
        const editor = input.closest(".meta-editor");
        if (editor.dataset.free && input.value.includes(",")) addTyped(editor, input);
        refresh(editor, input);
    });

    // Enter in the box and [+] beside it: a highlighted suggestion (for tags, one that starts with the typed
    // text) wins; otherwise tags take the typed text and categories the one leaf it names
    function commit(editor, input) {
        const option = menu(editor).hidden ? null : active(editor);
        if (editor.dataset.free) {
            const typed = input.value.trim().toLowerCase();
            if (option && (!typed || option.dataset.value.startsWith(typed))) pick(editor, option);
            else if (typed) { addTyped(editor, input); close(editor); }
            else { input.focus(); refresh(editor, input); } // nothing typed: open the list of tags in use
        } else {
            const choice = option || onlyMatch(editor, input);
            if (choice) { pick(editor, choice); return; }
            // nothing to add yet: open the list to choose from
            const typed = input.value.trim();
            note(editor, typed ? `no single category matches "${typed}": choose one from the list` : "choose a category from the list");
            input.focus();
            refresh(editor, input);
        }
    }

    document.addEventListener("keydown", e => {
        const input = e.target.closest(".meta-input");
        if (!input) return;
        const editor = input.closest(".meta-editor");
        const all = options(editor);
        const index = all.indexOf(active(editor));
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            if (!all.length) refresh(editor, input); // closed after a pick: the arrows open it again
            else highlight(editor, (index + (e.key === "ArrowDown" ? 1 : all.length - 1)) % all.length);
        } else if (e.key === "Escape") {
            if (!menu(editor).hidden) e.preventDefault(); // close the menu, not the dialog around it
            close(editor);
        } else if (e.key === "Enter") {
            e.preventDefault(); // Enter adds a chip; it never submits the form around the editor
            commit(editor, input);
        }
    });

    // mousedown, not click: it lands before the box loses focus and the menu closes
    document.addEventListener("mousedown", e => {
        // [+] must not take the focus either, or the menu (and its highlighted choice) is gone by the click
        if (e.target.closest(".meta-add")) { e.preventDefault(); return; }
        // nor the menu itself: grabbing its scrollbar would close it
        if (!e.target.closest(".meta-menu")) return;
        e.preventDefault();
        const option = e.target.closest(".meta-option");
        if (option) pick(option.closest(".meta-editor"), option);
    });

    document.addEventListener("click", e => {
        const plus = e.target.closest(".meta-add");
        if (plus) {
            const editor = plus.closest(".meta-editor");
            commit(editor, editor.querySelector(".meta-input"));
            return;
        }
        const remove = e.target.closest(".meta-remove");
        if (remove) {
            const editor = remove.closest(".meta-editor");
            remove.closest(".meta-chip").remove();
            note(editor, "");
            count(editor);
            return;
        }
        // in an ordered editor, clicking a chip makes it the first (the primary category)
        const c = e.target.closest(".meta-editor[data-ordered] .meta-chip");
        if (c) chips(c.closest(".meta-editor")).prepend(c);
    });

    // text still in a box when the form is sent becomes a chip first, so it is not silently dropped; this
    // capture listener runs before htmx's own submit handler reads the form
    document.addEventListener("submit", e => {
        for (const input of e.target.querySelectorAll(".meta-input")) {
            if (!input.value.trim()) continue;
            const editor = input.closest(".meta-editor");
            if (editor.dataset.free) addTyped(editor, input);
            else {
                const match = onlyMatch(editor, input);
                if (match) add(editor, match.dataset.value, match.dataset.label);
            }
        }
    }, true);

    // an open menu follows its box when the dialog (or the page) scrolls or the window is resized
    function placeOpen() {
        document.querySelectorAll(".meta-menu:not([hidden])").forEach(m => place(m.closest(".meta-editor")));
    }
    document.addEventListener("scroll", placeOpen, true);
    window.addEventListener("resize", placeOpen);

    document.addEventListener("DOMContentLoaded", () => countAll(document));
    document.addEventListener("htmx:load", e => countAll(e.target));

    // the message for a failed request: FastAPI's detail is a string, or a list for a 422; anything else is
    // a server error
    window.metaError = function (xhr) {
        try {
            const detail = JSON.parse(xhr.response).detail;
            if (typeof detail === "string") return detail;
            if (Array.isArray(detail)) return detail.map(d => d.msg || String(d)).join("; ");
        } catch (err) { /* not JSON */ }
        return `request failed (${xhr.status})`;
    };
})();
