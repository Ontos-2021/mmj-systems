document.documentElement.classList.replace("no-js", "js");

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

  window.matchMedia("(max-width: 48rem)").addEventListener("change", closeMenu);

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

const CONTACT_ENDPOINT = "https://api.mmjsystems.cl/contacto";
const CONTACT_EMAIL = "contacto.mmjsystems@gmail.com";
const CONTACT_CHANNELS = new Set(["linkedin", "email", "referido", "google", "meta", "whatsapp"]);
const CONTACT_MESSAGES = new Set(["ahorro-tiempo", "pendientes-sin-responsable"]);
const params = new URLSearchParams(location.search);
const channelParam = params.get("utm_source");
const angleParam = params.get("utm_content");
const channel = CONTACT_CHANNELS.has(channelParam) ? channelParam : null;
const angle = CONTACT_MESSAGES.has(angleParam) ? angleParam : null;

if (channel || angle) {
  for (const link of document.querySelectorAll("a[data-carry-campaign]")) {
    const destination = new URL(link.href);
    if (destination.origin !== location.origin) continue;
    if (channel) destination.searchParams.set("utm_source", channel);
    if (angle) destination.searchParams.set("utm_content", angle);
    link.href = destination.href;
  }
}

const form = document.querySelector("#contact-form");
if (form) {
  const isLive = location.protocol === "https:"
    && ["mmjsystems.cl", "www.mmjsystems.cl"].includes(location.hostname);
  const attribution = [
    `Página: ${form.dataset.contactSource}`,
    channel ? `Canal: ${channel}` : "",
    angle ? `Mensaje de campaña: ${angle}` : "",
  ].filter(Boolean).join("\n");

  const status = document.querySelector("#form-status");
  const say = (message) => {
    if (status) status.textContent = message;
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const message = String(data.get("mensaje") || "").trim();
    const payload = {
      nombre: String(data.get("nombre") || "").trim(),
      empresa: String(data.get("empresa") || "").trim(),
      email: String(data.get("email") || "").trim(),
      mensaje: `${message}\n\n${attribution}`,
      sitio: String(data.get("sitio") || "").trim(),
    };
    if (payload.nombre.length < 2 || !payload.email || message.length < 10) {
      say("Completa nombre, correo y una breve descripción del proceso.");
      return;
    }
    if (!isLive) {
      say("Prueba completada: no se envió ningún mensaje.");
      return;
    }
    const submit = form.querySelector('[type="submit"]');
    if (submit) submit.disabled = true;
    say("Enviando…");
    try {
      const response = await fetch(CONTACT_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error("bad-status");
      form.reset();
      say("Consulta enviada. Te responderemos por correo para coordinar.");
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

  if (!isLive) {
    const preview = document.createElement("p");
    preview.className = "form-preview";
    preview.textContent = "Vista de prueba: este formulario no envía mensajes.";
    form.prepend(preview);
  }
  form.hidden = false;
}
