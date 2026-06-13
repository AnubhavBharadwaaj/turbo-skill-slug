"""
Animation diagnostic for the shell iframe.

Embeds a self-reporting probe inside the iframe srcdoc that:
  1. Confirms the iframe document actually rendered (suspect #3)
  2. Counts <animate>/<animateTransform> elements present in the DOM (suspect #2:
     did Gradio strip them before they reached the iframe?)
  3. Uses the SVG SMIL API (svg.getCurrentTime / elem.getStartTime) to check
     whether the animations are actually RUNNING, not just present (suspect #4)
  4. Paints a visible badge in the corner with the verdict, so you SEE the answer
     on the live Space without opening devtools.

This makes the failure point unambiguous:
  - Badge never appears        -> iframe didn't render (suspect #3) OR Gradio
                                  didn't even pass the iframe through
  - Badge: "0 anim elements"   -> SMIL stripped before/at the iframe (suspect #2)
  - Badge: "N present, FROZEN"  -> SMIL present but not playing (suspect #4: sandbox)
  - Badge: "N present, RUNNING" -> animation IS working; the issue is it is too
                                  fast/subtle to see, or you looked after it froze
"""

PROBE_JS = """
<script>
(function(){
  function badge(text, color){
    var d = document.createElement('div');
    d.textContent = text;
    d.style.cssText = 'position:fixed;left:6px;bottom:6px;z-index:99999;'
      + 'font:11px monospace;padding:4px 7px;border-radius:4px;'
      + 'background:'+color+';color:#fff;opacity:0.92;pointer-events:none;'
      + 'white-space:nowrap;';
    document.body.appendChild(d);
  }
  function run(){
    var svg = document.querySelector('svg');
    if(!svg){ badge('NO SVG in iframe', '#b00'); return; }
    var anims = svg.querySelectorAll('animate, animateTransform, animateMotion');
    var n = anims.length;
    if(n === 0){ badge('SMIL STRIPPED: 0 anim elements', '#b00'); return; }
    // Check if SMIL is actually advancing time.
    var t0 = 0;
    try { t0 = svg.getCurrentTime(); } catch(e){
      badge(n+' present, but getCurrentTime() FAILED (SMIL unsupported)', '#b06000');
      return;
    }
    // Sample again shortly after; if currentTime advanced, SMIL is running.
    setTimeout(function(){
      var t1 = 0;
      try { t1 = svg.getCurrentTime(); } catch(e){}
      if(t1 > t0 + 0.05){
        badge(n+' anim elements, RUNNING (t='+t1.toFixed(2)+'s)', '#0a7d2c');
      } else {
        badge(n+' present, FROZEN (SMIL not advancing - sandbox?)', '#b06000');
      }
    }, 350);
  }
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', run);
  } else { run(); }
})();
</script>
"""


def inject_probe(iframe_inner_html: str) -> str:
    """Insert the probe <script> just before </body> inside the iframe document.

    iframe_inner_html is the FULL html doc string that goes into srcdoc (before
    escaping). The probe runs inside the iframe's own document, where SMIL lives.
    """
    if "</body>" in iframe_inner_html:
        return iframe_inner_html.replace("</body>", PROBE_JS + "</body>", 1)
    return iframe_inner_html + PROBE_JS
