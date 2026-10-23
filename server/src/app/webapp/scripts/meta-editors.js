// Metadata editors (tags, categories): chips that each carry a hidden form input, and a text box with a
// <datalist> to pick from. One delegated set of listeners serves every editor on the page, including
// editors htmx swaps in later.
(function () {
    if (window.metaEditors) return;
    window.metaEditors = true;

    function chip(editor, value, text) {
        const kind = editor.dataset.kind;
        const span = document.createElement("span");
        span.className = "meta-chip";
        span.dataset.value = value;
        const label = document.createElement("span");
        label.className = "meta-chip-label";
        label.textContent = text;
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = kind;
        input.value = value;
        span.append(label, input);
        if (editor.dataset.ordered) {
            span.append(button("[<]", "meta-left"), button("[>]", "meta-right"));
        }
        span.append(button("[x]", "meta-remove"));
        return span;
    }

    function button(text, cls) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = cls + " text-dim hover:bg-paper hover:text-ink";
        b.textContent = text;
        return b;
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
        note(editor, "");
    }

    // tags: Enter or a comma turns the typed text into a chip
    function addTyped(editor, input) {
        for (const raw of input.value.split(",")) {
            const tag = raw.trim().toLowerCase().replace(/\s+/g, "-");
            if (tag) add(editor, tag, tag);
        }
        input.value = "";
    }

    // categories: only a label from the datalist becomes a chip; it carries the option's path
    function addPicked(editor, input) {
        const option = [...editor.querySelectorAll("datalist option")].find(o => o.value === input.value);
        if (!option) return false;
        add(editor, option.dataset.path, option.value);
        input.value = "";
        return true;
    }

    let timer;
    document.addEventListener("input", e => {
        const input = e.target.closest(".meta-input");
        if (!input) return;
        const editor = input.closest(".meta-editor");
        if (editor.dataset.free) {
            if (input.value.includes(",")) addTyped(editor, input);
            const url = editor.dataset.suggest;
            if (!url) return;
            clearTimeout(timer);
            timer = setTimeout(async () => {
                const r = await fetch(url + "?q=" + encodeURIComponent(input.value.trim()));
                if (r.ok) editor.querySelector("datalist").innerHTML = await r.text();
            }, 150);
        } else {
            addPicked(editor, input);
        }
    });

    document.addEventListener("keydown", e => {
        const input = e.target.closest(".meta-input");
        if (!input || e.key !== "Enter") return;
        e.preventDefault(); // Enter adds a chip; it never submits the form around the editor
        const editor = input.closest(".meta-editor");
        if (editor.dataset.free) addTyped(editor, input);
        else if (!addPicked(editor, input)) note(editor, "pick one of the listed categories");
    });

    document.addEventListener("click", e => {
        const b = e.target.closest(".meta-remove, .meta-left, .meta-right");
        if (!b) return;
        const c = b.closest(".meta-chip");
        const editor = c.closest(".meta-editor");
        if (b.classList.contains("meta-remove")) c.remove();
        else if (b.classList.contains("meta-left") && c.previousElementSibling) c.after(c.previousElementSibling);
        else if (b.classList.contains("meta-right") && c.nextElementSibling) c.before(c.nextElementSibling);
        note(editor, "");
    });

    // text still in a box when the form is sent becomes a chip first, so it is not silently dropped; this
    // capture listener runs before htmx's own submit handler reads the form
    document.addEventListener("submit", e => {
        for (const input of e.target.querySelectorAll(".meta-input")) {
            if (!input.value.trim()) continue;
            const editor = input.closest(".meta-editor");
            if (editor.dataset.free) addTyped(editor, input);
            else addPicked(editor, input);
        }
    }, true);

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
