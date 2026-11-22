(() => {
  const story = document.querySelector("[data-scroll-story]");
  if (!story) return;

  const frame = story.querySelector("[data-story-frame]");
  const stage = story.querySelector(".story-stage");
  const chapters = story.querySelector(".story-chapters");
  const steps = Array.from(chapters.children);
  const counter = story.querySelector("[data-story-count]");
  const toggle = story.querySelector(".story-toggle");
  const header = document.querySelector(".site-header");
  const photos = document.querySelectorAll("[data-depth-photo]");
  const canScrub = Boolean(document.createElement("video").canPlayType('video/mp4; codecs="avc1.640028"'));
  const mobile = matchMedia("(max-width: 56rem)");
  const compact = matchMedia("(max-height: 24rem), (max-width: 56rem) and (max-height: 33rem)");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const connection = navigator.connection;
  const clamp = (value) => Math.max(0, Math.min(1, value));

  let enabled = false;
  let staticView = false;
  let failed = false;
  let engaged = window.scrollY > 0;
  let animation = 0;
  let active = -1;
  let request;
  let loadDeadline;
  let video;
  let objectUrl;

  function paintDepth(height, headerHeight) {
    const hero = story.getBoundingClientRect();
    if (hero.bottom > 0 && hero.top < height) {
      const progress = clamp((headerHeight - hero.top) / Math.max(1, hero.height - height));
      story.style.setProperty("--depth-progress", progress);
    }
    for (const photo of photos) {
      const bounds = photo.getBoundingClientRect();
      if (bounds.bottom <= 0 || bounds.top >= height) continue;
      const progress = clamp((height - bounds.top) / (height + bounds.height));
      photo.style.setProperty("--photo-offset", progress - 0.5);
    }
  }

  function discardMedia() {
    clearTimeout(loadDeadline);
    request?.abort();
    request = undefined;
    if (video) {
      const oldVideo = video;
      video = undefined;
      oldVideo.remove();
      oldVideo.removeAttribute("src");
      oldVideo.load();
    }
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = undefined;
    frame.removeAttribute("data-painted");
  }

  function showFallback() {
    failed = true;
    updateMode();
  }

  async function loadMedia() {
    const pending = new AbortController();
    request = pending;
    loadDeadline = setTimeout(() => {
      if (request === pending) showFallback();
    }, 20000);
    try {
      const source = mobile.matches ? frame.dataset.mobile : frame.dataset.desktop;
      // A local Blob allows backward seeks even on static servers without Range support.
      const response = await fetch(source, { signal: pending.signal, priority: "low" });
      if (!response.ok) throw new Error("Story clip unavailable");
      const blob = await response.blob();
      if (pending.signal.aborted || request !== pending) return;

      objectUrl = URL.createObjectURL(blob);
      const clip = document.createElement("video");
      video = clip;
      clip.setAttribute("aria-hidden", "true");
      clip.defaultMuted = true;
      clip.muted = true;
      clip.playsInline = true;
      clip.preload = "auto";
      clip.disablePictureInPicture = true;
      clip.addEventListener("loadedmetadata", schedule);
      clip.addEventListener("loadeddata", () => {
        if (video === clip) {
          clearTimeout(loadDeadline);
          schedule();
        }
      });
      clip.addEventListener("seeked", () => {
        if (video !== clip) return;
        if (clip.readyState >= 2) frame.setAttribute("data-painted", "");
        schedule();
      });
      clip.addEventListener("error", () => {
        if (video === clip) showFallback();
      }, { once: true });
      frame.append(clip);
      clip.src = objectUrl;
    } catch {
      if (!pending.signal.aborted && request === pending) showFallback();
    }
  }

  function paintStory(progress, current) {
    if (current !== active) {
      steps[active]?.removeAttribute("data-current");
      steps[current].setAttribute("data-current", "");
      active = current;
      counter.textContent = `0${current + 1} / 0${steps.length}`;
    }
    story.style.setProperty("--story-progress", progress);
    // The poster is the first frame; keep it visible until a seek finishes.
    frame.toggleAttribute("data-at-start", progress === 0);
  }

  function seekVideo(progress) {
    if (!video || video.seeking || !Number.isFinite(video.duration)) return;
    const target = progress * Math.max(0, video.duration - 0.042);
    if (Math.abs(video.currentTime - target) > 0.019) {
      try {
        video.currentTime = target;
      } catch {
        showFallback();
      }
    }
  }

  function updateStory(height, headerHeight) {
    if (!engaged) return;
    const region = chapters.getBoundingClientRect();
    if (region.bottom <= 0) return;
    if (region.top > height + 180) {
      paintStory(0, 0);
      seekVideo(0);
      return;
    }
    // On phones the reading line is below the pinned film, on desktop beside it.
    const line = mobile.matches
      ? Math.min(height - 46, headerHeight + stage.offsetHeight + 34)
      : height * 0.56;
    const last = steps[steps.length - 1].getBoundingClientRect();
    const end = last.bottom - last.height * 0.3;
    const progress = clamp((line - region.top) / Math.max(1, end - region.top));
    let current = 0;
    for (let index = 1; index < steps.length; index++) {
      if (steps[index].getBoundingClientRect().top > line) break;
      current = index;
    }
    paintStory(progress, current);
    if (!request) void loadMedia();
    seekVideo(progress);
  }

  function update() {
    animation = 0;
    if (!enabled) return;
    const height = window.innerHeight;
    const headerHeight = header.offsetHeight;
    paintDepth(height, headerHeight);
    updateStory(height, headerHeight);
  }

  function schedule() {
    if (enabled && !animation) animation = requestAnimationFrame(update);
  }

  function updateMode() {
    const available = canScrub && !failed && !reduced.matches && !compact.matches && !connection?.saveData;
    enabled = available && !staticView;
    toggle.hidden = !available;
    toggle.setAttribute("aria-pressed", String(staticView));
    document.documentElement.toggleAttribute("data-depth-motion", enabled);
    story.toggleAttribute("data-motion", enabled);
    if (enabled) schedule();
    else {
      cancelAnimationFrame(animation);
      animation = 0;
      discardMedia();
    }
  }

  toggle.addEventListener("click", () => {
    staticView = !staticView;
    updateMode();
  });
  window.addEventListener("scroll", () => {
    if (window.scrollY > 0) engaged = true;
    schedule();
  }, { passive: true });
  window.addEventListener("resize", schedule);
  window.addEventListener("pagehide", () => {
    enabled = false;
    cancelAnimationFrame(animation);
    animation = 0;
    discardMedia();
  });
  window.addEventListener("pageshow", updateMode);
  mobile.addEventListener("change", () => {
    discardMedia();
    failed = false;
    updateMode();
  });
  reduced.addEventListener("change", updateMode);
  compact.addEventListener("change", updateMode);
  connection?.addEventListener?.("change", updateMode);
  updateMode();
})();
