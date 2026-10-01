(function () {
  'use strict';
  var toggle = document.querySelector('.menu-toggle');
  var nav = document.getElementById('main-nav');
  function closeMenu() { if (!nav || !toggle) return; nav.classList.remove('is-open'); toggle.setAttribute('aria-expanded', 'false'); }
  if (toggle && nav) {
    toggle.addEventListener('click', function () { var open = toggle.getAttribute('aria-expanded') !== 'true'; toggle.setAttribute('aria-expanded', String(open)); nav.classList.toggle('is-open', open); });
    nav.addEventListener('click', function (e) { if (e.target.closest('a')) closeMenu(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') { closeMenu(); toggle.focus(); } });
    document.addEventListener('click', function (e) { if (!e.target.closest('.site-header')) closeMenu(); });
    window.addEventListener('resize', function () { if (window.innerWidth > 800) closeMenu(); });
  }
  var video = document.getElementById('hero-video');
  var control = document.getElementById('hero-toggle');
  if (!video || !control) return;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  function reflect() { var paused = video.paused; control.innerHTML = (paused ? '▷' : 'Ⅱ') + ' <span>' + (paused ? '영상 재생' : '일시정지') + '</span>'; control.setAttribute('aria-label', '배경 영상 ' + (paused ? '재생' : '일시정지')); }
  function play() { var promise = video.play(); if (promise && promise.catch) promise.catch(reflect); }
  function fail() { video.style.visibility = 'hidden'; video.parentElement.style.backgroundImage = 'url("' + video.poster + '")'; video.parentElement.style.backgroundSize = 'cover'; video.parentElement.style.backgroundPosition = 'center'; control.hidden = true; }
  video.addEventListener('play', reflect); video.addEventListener('pause', reflect); video.addEventListener('error', fail);
  var source = video.querySelector('source'); if (source) source.addEventListener('error', fail);
  control.addEventListener('click', function () { if (video.paused) play(); else video.pause(); });
  function motionChange() { if (reduced.matches) video.pause(); }
  if (reduced.addEventListener) reduced.addEventListener('change', motionChange);
  if (!reduced.matches) play(); else reflect();
})();
