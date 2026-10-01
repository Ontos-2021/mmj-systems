document.documentElement.classList.replace("no-js", "js");
requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    document.body.classList.add("is-loaded");
  });
});

const menuButton = document.querySelector(".menu-button");
const navigation = document.querySelector("#navigation");

if (menuButton && navigation) {
  const closeMenu = () => {
    menuButton.setAttribute("aria-expanded", "false");
    navigation.removeAttribute("data-open");
    document.body.style.overflow = "";
  };

  menuButton.addEventListener("click", () => {
    const isOpen = menuButton.getAttribute("aria-expanded") === "true";
    menuButton.setAttribute("aria-expanded", String(!isOpen));
    navigation.toggleAttribute("data-open", !isOpen);
    document.body.style.overflow = !isOpen ? "hidden" : "";
  });

  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) closeMenu();
  });

  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      menuButton.getAttribute("aria-expanded") === "true"
    ) {
      closeMenu();
      menuButton.focus();
    }
  });
}

const year = document.querySelector("[data-year]");
if (year) year.textContent = String(new Date().getFullYear());

const frictionItems = document.querySelectorAll(".friction-list li");
if (frictionItems.length) {
  if ("IntersectionObserver" in window) {
    const reveal = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            reveal.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2, rootMargin: "0px 0px -8% 0px" },
    );
    frictionItems.forEach((item) => reveal.observe(item));
  } else {
    frictionItems.forEach((item) => item.classList.add("is-visible"));
  }
}

const flowDiagram = document.querySelector(".flow-diagram");
if (flowDiagram) {
  if ("IntersectionObserver" in window) {
    const flowReveal = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            flowReveal.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.3 },
    );
    flowReveal.observe(flowDiagram);
  } else {
    flowDiagram.classList.add("is-visible");
  }
}

const revealItems = document.querySelectorAll(
  ".capability-accordion details, .evidence-item, .process-list li",
);
if (revealItems.length) {
  if ("IntersectionObserver" in window) {
    const revealAll = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            revealAll.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2, rootMargin: "0px 0px -8% 0px" },
    );
    revealItems.forEach((item) => revealAll.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add("is-visible"));
  }
}

const workNote = document.querySelector(".work-note");
const heroSection = document.querySelector(".hero");
const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

if (workNote && heroSection && finePointer.matches && !reducedMotion.matches) {
  const MAX_TILT = 7;
  let tiltRaf = 0;
  const clampHalf = (value) => Math.max(-0.5, Math.min(0.5, value));

  heroSection.addEventListener("pointermove", (event) => {
    if (tiltRaf) return;
    tiltRaf = requestAnimationFrame(() => {
      tiltRaf = 0;
      const rect = workNote.getBoundingClientRect();
      const px = clampHalf((event.clientX - (rect.left + rect.width / 2)) / rect.width);
      const py = clampHalf((event.clientY - (rect.top + rect.height / 2)) / rect.height);
      const tiltY = px * MAX_TILT * 2;
      const tiltX = py * -MAX_TILT * 2;
      workNote.style.setProperty("--tilt-x", `${tiltX.toFixed(2)}deg`);
      workNote.style.setProperty("--tilt-y", `${tiltY.toFixed(2)}deg`);
      workNote.style.boxShadow = `${(14.4 - tiltY * 0.8).toFixed(1)}px ${(17.6 + tiltX * 0.8).toFixed(1)}px 0 rgba(48, 36, 29, 0.13)`;
    });
  });

  heroSection.addEventListener("pointerleave", () => {
    if (tiltRaf) {
      cancelAnimationFrame(tiltRaf);
      tiltRaf = 0;
    }
    workNote.style.setProperty("--tilt-x", "0deg");
    workNote.style.setProperty("--tilt-y", "0deg");
    workNote.style.boxShadow = "";
  });
}

const coarsePointer = window.matchMedia("(hover: none), (pointer: coarse), (max-width: 48rem)");
if (workNote && coarsePointer.matches && !reducedMotion.matches) {
  const TOUCH_TILT = 10;
  let touchRaf = 0;
  const setTouchTilt = (clientX, clientY) => {
    const rect = workNote.getBoundingClientRect();
    const px = Math.max(-0.5, Math.min(0.5, (clientX - (rect.left + rect.width / 2)) / rect.width));
    const py = Math.max(-0.5, Math.min(0.5, (clientY - (rect.top + rect.height / 2)) / rect.height));
    workNote.style.setProperty("--tilt-x", `${(py * -TOUCH_TILT * 2).toFixed(2)}deg`);
    workNote.style.setProperty("--tilt-y", `${(px * TOUCH_TILT * 2).toFixed(2)}deg`);
  };
  const resetTouchTilt = () => {
    if (touchRaf) {
      cancelAnimationFrame(touchRaf);
      touchRaf = 0;
    }
    workNote.classList.remove("is-touching");
    workNote.style.setProperty("--tilt-x", "0deg");
    workNote.style.setProperty("--tilt-y", "0deg");
  };
  workNote.addEventListener("touchstart", (event) => {
    workNote.classList.add("is-touching");
    const touch = event.touches[0];
    setTouchTilt(touch.clientX, touch.clientY);
  }, { passive: true });
  workNote.addEventListener("touchmove", (event) => {
    if (touchRaf) return;
    const touch = event.touches[0];
    touchRaf = requestAnimationFrame(() => {
      touchRaf = 0;
      setTouchTilt(touch.clientX, touch.clientY);
    });
  }, { passive: true });
  workNote.addEventListener("touchend", resetTouchTilt);
  workNote.addEventListener("touchcancel", resetTouchTilt);
}

const CONTACT_ENDPOINT = "https://api.mmjsystems.cl/contacto";
const CONTACT_EMAIL = "contacto.mmjsystems@gmail.com";

const copyButton = document.querySelector("[data-copy]");
if (copyButton) {
  copyButton.addEventListener("click", async () => {
    const text = copyButton.getAttribute("data-copy") || CONTACT_EMAIL;
    let done = false;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        done = true;
      } catch {
        done = false;
      }
    }
    if (!done) {
      const field = document.createElement("textarea");
      field.value = text;
      document.body.appendChild(field);
      field.select();
      try {
        done = document.execCommand("copy");
      } catch {
        done = false;
      }
      field.remove();
    }
    const original = copyButton.textContent;
    copyButton.textContent = done ? "Copiado ✓" : "Copia manual: " + text;
    window.setTimeout(() => {
      copyButton.textContent = original;
    }, 2500);
  });
}

const form = document.querySelector("#contact-form");
if (form) {
  if (!form.getAttribute("action")) form.setAttribute("action", CONTACT_ENDPOINT);
  const status = document.querySelector("#form-status");
  const say = (message) => {
    if (status) status.textContent = message;
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const payload = {
      nombre: String(data.get("nombre") || "").trim(),
      empresa: String(data.get("empresa") || "").trim(),
      email: String(data.get("email") || "").trim(),
      mensaje: String(data.get("mensaje") || "").trim(),
      sitio: String(data.get("sitio") || "").trim(),
    };
    if (!payload.nombre || !payload.email || !payload.mensaje) {
      say("Completa nombre, correo y mensaje para enviar.");
      return;
    }
    const submit = form.querySelector('[type="submit"]');
    if (submit) submit.disabled = true;
    say("Enviando…");
    try {
      const response = await fetch(form.getAttribute("action") || CONTACT_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error("bad-status");
      form.reset();
      say("Mensaje enviado. Te respondemos a la brevedad.");
    } catch {
      const subject = encodeURIComponent("Conversación inicial con MMJ Systems");
      const body = encodeURIComponent(
        payload.nombre + " (" + payload.email + ")" +
        (payload.empresa ? " — " + payload.empresa : "") +
        "\n\n" + payload.mensaje,
      );
      say("No se pudo enviar el formulario. Escríbenos directo: ");
      if (status) {
        const link = document.createElement("a");
        link.href = "mailto:" + CONTACT_EMAIL + "?subject=" + subject + "&body=" + body;
        link.textContent = CONTACT_EMAIL;
        status.appendChild(link);
      }
    } finally {
      if (submit) submit.disabled = false;
    }
  });
}
