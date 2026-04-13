# HTML/CSS de la landing pre-login (publicidad). Mantener contenido comercial aca para no inflar main.py.

from textwrap import dedent


def obtener_html_landing_publicidad(logo_html: str) -> str:
    """Retorna el bloque completo <style> + markup para st.markdown(..., unsafe_allow_html=True)."""
    parts = [
        dedent(
            """
            <style>
              @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,600;0,9..144,700;0,9..144,800;1,9..144,600&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

              :root {
                --lp-void: #050812;
                --lp-panel: rgba(11, 18, 31, 0.82);
                --lp-panel-soft: rgba(15, 24, 40, 0.72);
                --lp-panel-strong: rgba(17, 28, 47, 0.96);
                --lp-line: rgba(125, 211, 252, 0.18);
                --lp-line-strong: rgba(45, 212, 191, 0.32);
                --lp-text: #f4f7fb;
                --lp-muted: #97a7be;
                --lp-accent: #2dd4bf;
                --lp-blue: #60a5fa;
                --lp-gold: #fbbf24;
                --lp-shadow: 0 26px 70px rgba(0, 0, 0, 0.32);
              }

              .mc-lp {
                position: relative;
                isolation: isolate;
                overflow-x: clip;
                color: var(--lp-text);
                font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
              }

              .mc-lp * {
                box-sizing: border-box;
              }

              .mc-lp-bg {
                position: fixed;
                inset: 0;
                z-index: -2;
                background:
                  radial-gradient(circle at 14% 16%, rgba(45, 212, 191, 0.12), transparent 26%),
                  radial-gradient(circle at 86% 10%, rgba(96, 165, 250, 0.12), transparent 30%),
                  radial-gradient(circle at 50% 100%, rgba(45, 212, 191, 0.08), transparent 28%),
                  linear-gradient(180deg, #04070d 0%, #07101a 100%);
              }

              .mc-lp-bg::after {
                content: "";
                position: absolute;
                inset: 0;
                opacity: 0.32;
                background-image:
                  linear-gradient(rgba(148, 163, 184, 0.045) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(148, 163, 184, 0.045) 1px, transparent 1px);
                background-size: 52px 52px;
                mask-image: radial-gradient(circle at 50% 38%, black 0%, rgba(0, 0, 0, 0.92) 42%, transparent 88%);
              }

              .mc-lp-inner {
                max-width: 1240px;
                margin: 0 auto;
                padding: 52px 24px 32px;
              }

              .mc-lp-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 18px;
                flex-wrap: wrap;
                margin-bottom: 34px;
              }

              .mc-lp-brand {
                display: flex;
                align-items: center;
                gap: 18px;
              }

              .mc-lp-logo-wrap {
                padding: 16px 18px;
                border-radius: 24px;
                background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.92));
                box-shadow: 0 20px 55px rgba(0, 0, 0, 0.36);
              }

              .mc-lp-brand-kicker {
                display: block;
                margin-bottom: 4px;
                font-size: 0.74rem;
                font-weight: 800;
                letter-spacing: 0.2em;
                text-transform: uppercase;
                color: var(--lp-accent);
              }

              .mc-lp-brand-name {
                margin: 0;
                color: #ffffff;
                font-family: 'Fraunces', Georgia, serif;
                font-size: 1.55rem;
                font-weight: 700;
                letter-spacing: -0.03em;
                line-height: 1.05;
              }

              .mc-lp-header-badge {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                min-height: 42px;
                padding: 0 16px;
                border: 1px solid var(--lp-line);
                border-radius: 999px;
                background: rgba(6, 12, 22, 0.58);
                color: #d8e3f2;
                font-size: 0.8rem;
                font-weight: 700;
                letter-spacing: 0.04em;
                backdrop-filter: blur(12px);
              }

              .mc-lp-hero {
                display: grid;
                grid-template-columns: minmax(0, 1.15fr) minmax(340px, 0.85fr);
                gap: 28px;
                align-items: stretch;
                margin-bottom: 24px;
              }

              .mc-lp-copy {
                position: relative;
                padding: 34px 34px 30px;
                border-radius: 30px;
                background:
                  linear-gradient(180deg, rgba(8, 14, 26, 0.82), rgba(6, 12, 22, 0.72)),
                  radial-gradient(circle at top left, rgba(45, 212, 191, 0.08), transparent 28%);
                border: 1px solid rgba(148, 163, 184, 0.1);
                box-shadow: var(--lp-shadow);
                overflow: hidden;
              }

              .mc-lp-copy::before {
                content: "";
                position: absolute;
                left: 0;
                top: 26px;
                bottom: 26px;
                width: 3px;
                border-radius: 3px;
                background: linear-gradient(180deg, var(--lp-accent), var(--lp-blue));
              }

              .mc-lp-copy::after {
                content: "";
                position: absolute;
                right: -120px;
                top: -140px;
                width: 320px;
                height: 320px;
                background: radial-gradient(circle, rgba(96, 165, 250, 0.12), transparent 68%);
                pointer-events: none;
              }

              .mc-lp-kicker {
                margin: 0 0 16px;
                color: #b6c3d8;
                font-size: 0.8rem;
                font-weight: 800;
                letter-spacing: 0.2em;
                text-transform: uppercase;
              }

              .mc-lp-h1 {
                margin: 0 0 18px;
                max-width: 11.5ch;
                color: #ffffff;
                font-family: 'Fraunces', Georgia, serif;
                font-size: clamp(2.55rem, 5vw, 4.35rem);
                font-weight: 800;
                line-height: 0.98;
                letter-spacing: -0.05em;
              }

              .mc-lp-h1 em {
                display: inline-block;
                font-style: italic;
                font-weight: 700;
                background: linear-gradient(120deg, #67e8f9 0%, #7dd3fc 28%, #5eead4 100%);
                -webkit-background-clip: text;
                background-clip: text;
                -webkit-text-fill-color: transparent;
              }

              .mc-lp-lead {
                margin: 0 0 24px;
                max-width: 40rem;
                color: #b9c7d8;
                font-size: 1.07rem;
                line-height: 1.82;
                font-weight: 500;
              }

              .mc-lp-pill-row {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 20px;
              }

              .mc-lp-pill {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                min-height: 42px;
                padding: 0 15px;
                border-radius: 999px;
                border: 1px solid rgba(148, 163, 184, 0.14);
                background: rgba(8, 13, 23, 0.68);
                color: #d7e2ef;
                font-size: 0.82rem;
                font-weight: 700;
              }

              .mc-lp-pill strong {
                color: var(--lp-accent);
                font-weight: 800;
              }

              .mc-lp-proof-row {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 12px;
              }

              .mc-lp-proof {
                padding: 14px 14px 13px;
                border-radius: 18px;
                border: 1px solid rgba(148, 163, 184, 0.12);
                background: rgba(10, 16, 29, 0.78);
                backdrop-filter: blur(10px);
              }

              .mc-lp-proof b {
                display: block;
                margin-bottom: 4px;
                color: #f7fbff;
                font-size: 0.92rem;
                font-weight: 800;
              }

              .mc-lp-proof span {
                color: var(--lp-muted);
                font-size: 0.8rem;
                line-height: 1.45;
              }

              .mc-lp-board {
                position: relative;
                padding: 22px;
                border-radius: 30px;
                background:
                  linear-gradient(180deg, rgba(12, 20, 35, 0.95), rgba(6, 10, 18, 0.98)),
                  radial-gradient(circle at top right, rgba(45, 212, 191, 0.08), transparent 32%);
                border: 1px solid rgba(96, 165, 250, 0.14);
                box-shadow: var(--lp-shadow);
                overflow: hidden;
              }

              .mc-lp-board-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 16px;
              }

              .mc-lp-board-kicker {
                color: #c9d7e8;
                font-size: 0.82rem;
                font-weight: 800;
                letter-spacing: 0.14em;
                text-transform: uppercase;
              }

              .mc-lp-board-badge {
                display: inline-flex;
                align-items: center;
                min-height: 34px;
                padding: 0 12px;
                border-radius: 999px;
                background: rgba(45, 212, 191, 0.12);
                color: #8ef2e3;
                font-size: 0.75rem;
                font-weight: 800;
                letter-spacing: 0.12em;
                text-transform: uppercase;
              }

              .mc-lp-board-title {
                margin: 0 0 18px;
                color: #ffffff;
                font-family: 'Fraunces', Georgia, serif;
                font-size: 1.5rem;
                font-weight: 700;
                letter-spacing: -0.03em;
              }
            """
        ),
        dedent(
            """
              .mc-lp-flow {
                display: flex;
                flex-direction: column;
                gap: 12px;
              }

              .mc-lp-flow-card {
                display: grid;
                grid-template-columns: 14px 1fr auto;
                gap: 14px;
                align-items: center;
                padding: 18px 18px;
                border-radius: 20px;
                border: 1px solid rgba(148, 163, 184, 0.1);
                background: rgba(19, 29, 47, 0.86);
              }

              .mc-lp-dot {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                box-shadow: 0 0 18px currentColor;
              }

              .mc-lp-dot.a { color: var(--lp-accent); background: var(--lp-accent); }
              .mc-lp-dot.b { color: var(--lp-blue); background: var(--lp-blue); }
              .mc-lp-dot.c { color: var(--lp-gold); background: var(--lp-gold); }
              .mc-lp-dot.d { color: #fb7185; background: #fb7185; }

              .mc-lp-flow-main b {
                display: block;
                margin-bottom: 4px;
                color: #ffffff;
                font-size: 0.96rem;
                font-weight: 800;
              }

              .mc-lp-flow-main span {
                color: var(--lp-muted);
                font-size: 0.82rem;
                line-height: 1.5;
              }

              .mc-lp-flow-tag {
                display: inline-flex;
                align-items: center;
                min-height: 32px;
                padding: 0 10px;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.04);
                color: #d7e4f3;
                font-size: 0.74rem;
                font-weight: 800;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                white-space: nowrap;
              }

              .mc-lp-board-foot {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 10px;
                margin-top: 14px;
              }

              .mc-lp-board-mini {
                padding: 14px 14px 12px;
                border-radius: 16px;
                background: rgba(8, 13, 23, 0.72);
                border: 1px solid rgba(148, 163, 184, 0.08);
              }

              .mc-lp-board-mini b {
                display: block;
                margin-bottom: 3px;
                color: #eef6ff;
                font-size: 0.84rem;
                font-weight: 800;
              }

              .mc-lp-board-mini span {
                color: var(--lp-muted);
                font-size: 0.75rem;
                line-height: 1.45;
              }

              .mc-lp-stats {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 14px;
                margin: 0 0 46px;
              }

              .mc-lp-stat {
                position: relative;
                padding: 22px 20px 18px;
                border-radius: 22px;
                border: 1px solid rgba(148, 163, 184, 0.12);
                background: var(--lp-panel-soft);
                box-shadow: 0 14px 40px rgba(0, 0, 0, 0.16);
                overflow: hidden;
              }

              .mc-lp-stat::before {
                content: "";
                position: absolute;
                left: 20px;
                right: 20px;
                top: 0;
                height: 2px;
                border-radius: 999px;
                background: linear-gradient(90deg, var(--lp-accent), var(--lp-blue));
              }

              .mc-lp-stat-value {
                margin: 0 0 8px;
                color: #ffffff;
                font-family: 'Fraunces', Georgia, serif;
                font-size: 2rem;
                font-weight: 700;
                letter-spacing: -0.04em;
                line-height: 1;
              }

              .mc-lp-stat-title {
                margin: 0 0 6px;
                color: #edf5fd;
                font-size: 0.92rem;
                font-weight: 800;
              }

              .mc-lp-stat-copy {
                margin: 0;
                color: var(--lp-muted);
                font-size: 0.8rem;
                line-height: 1.55;
              }

              .mc-lp-section-head {
                margin-bottom: 22px;
              }

              .mc-lp-section-kicker {
                display: inline-block;
                margin-bottom: 10px;
                color: #83deda;
                font-size: 0.76rem;
                font-weight: 800;
                letter-spacing: 0.18em;
                text-transform: uppercase;
              }

              .mc-lp-section-title {
                margin: 0 0 8px;
                color: #ffffff;
                font-family: 'Fraunces', Georgia, serif;
                font-size: 1.8rem;
                font-weight: 700;
                letter-spacing: -0.03em;
              }

              .mc-lp-section-sub {
                margin: 0;
                max-width: 48rem;
                color: var(--lp-muted);
                font-size: 1rem;
                line-height: 1.75;
              }
            """
        ),
        dedent(
            """
              .mc-lp-bento {
                display: grid;
                grid-template-columns: repeat(12, minmax(0, 1fr));
                gap: 16px;
                margin-bottom: 44px;
              }

              .mc-lp-cell {
                height: 100%;
                padding: 24px 22px;
                border-radius: 24px;
                border: 1px solid rgba(148, 163, 184, 0.12);
                background: var(--lp-panel);
                box-shadow: 0 18px 44px rgba(0, 0, 0, 0.16);
                transition: transform 0.22s ease, border-color 0.22s ease;
              }

              .mc-lp-cell:hover {
                transform: translateY(-4px);
                border-color: var(--lp-line-strong);
              }

              .mc-lp-cell-hero {
                grid-column: span 6;
                background:
                  linear-gradient(145deg, rgba(12, 20, 35, 0.96), rgba(8, 14, 25, 0.9)),
                  radial-gradient(circle at top right, rgba(45, 212, 191, 0.08), transparent 32%);
              }

              .mc-lp-cell-wide {
                grid-column: span 6;
              }

              .mc-lp-cell-mini {
                grid-column: span 4;
              }

              .mc-lp-cell-eyebrow {
                display: inline-block;
                margin-bottom: 10px;
                color: #8ce8dc;
                font-size: 0.72rem;
                font-weight: 800;
                letter-spacing: 0.18em;
                text-transform: uppercase;
              }

              .mc-lp-cell h4 {
                margin: 0 0 10px;
                color: #ffffff;
                font-size: 1.08rem;
                font-weight: 800;
                letter-spacing: -0.02em;
              }

              .mc-lp-cell p {
                margin: 0;
                color: var(--lp-muted);
                font-size: 0.94rem;
                line-height: 1.7;
              }

              .mc-lp-cell-list {
                display: grid;
                gap: 10px;
                margin-top: 16px;
              }

              .mc-lp-cell-item {
                padding: 12px 14px;
                border-radius: 14px;
                border: 1px solid rgba(148, 163, 184, 0.1);
                background: rgba(7, 13, 23, 0.5);
                color: #dce7f3;
                font-size: 0.86rem;
                font-weight: 600;
              }

              .mc-lp-cell-item strong {
                color: #ffffff;
              }

              .mc-lp-two-up {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 16px;
                margin-bottom: 44px;
              }

              .mc-lp-panel {
                padding: 28px 26px;
                border-radius: 26px;
                border: 1px solid rgba(148, 163, 184, 0.12);
                background: linear-gradient(180deg, rgba(14, 22, 36, 0.9), rgba(9, 15, 24, 0.88));
                box-shadow: 0 20px 48px rgba(0, 0, 0, 0.18);
              }

              .mc-lp-panel h3 {
                margin: 0 0 10px;
                color: #ffffff;
                font-family: 'Fraunces', Georgia, serif;
                font-size: 1.45rem;
                font-weight: 700;
                letter-spacing: -0.03em;
              }

              .mc-lp-panel p {
                margin: 0;
                color: var(--lp-muted);
                font-size: 0.98rem;
                line-height: 1.75;
              }

              .mc-lp-checks {
                display: grid;
                gap: 10px;
                margin-top: 18px;
              }

              .mc-lp-check {
                padding: 13px 14px;
                border-radius: 14px;
                border: 1px solid rgba(148, 163, 184, 0.1);
                background: rgba(8, 13, 23, 0.56);
                color: #d7e4f4;
                font-size: 0.9rem;
                font-weight: 600;
              }

              .mc-lp-check::before {
                content: "✓";
                margin-right: 10px;
                color: var(--lp-accent);
                font-weight: 900;
              }

              .mc-lp-mini-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 14px;
                margin-bottom: 44px;
              }

              .mc-lp-mini-card {
                padding: 20px 18px;
                border-radius: 18px;
                border: 1px solid rgba(148, 163, 184, 0.1);
                background: rgba(8, 13, 23, 0.64);
                transition: transform 0.2s ease, border-color 0.2s ease;
              }

              .mc-lp-mini-card:hover {
                transform: translateY(-3px);
                border-color: rgba(45, 212, 191, 0.32);
              }

              .mc-lp-mini-card b {
                display: block;
                margin-bottom: 7px;
                color: #ffffff;
                font-size: 0.98rem;
                font-weight: 800;
              }

              .mc-lp-mini-card span {
                color: var(--lp-muted);
                font-size: 0.85rem;
                line-height: 1.58;
              }
            """
        ),
        dedent(
            """
              .mc-lp-contact {
                position: relative;
                overflow: hidden;
                padding: 42px 30px 30px;
                border-radius: 30px;
                border: 1px solid rgba(45, 212, 191, 0.24);
                background:
                  linear-gradient(180deg, rgba(11, 18, 31, 0.95), rgba(6, 10, 18, 0.98)),
                  radial-gradient(circle at top right, rgba(45, 212, 191, 0.1), transparent 26%);
                box-shadow: var(--lp-shadow);
              }

              .mc-lp-contact::before {
                content: "";
                position: absolute;
                width: 320px;
                height: 320px;
                right: -120px;
                top: -120px;
                background: radial-gradient(circle, rgba(45, 212, 191, 0.12), transparent 70%);
                pointer-events: none;
              }

              .mc-lp-contact-head {
                margin-bottom: 24px;
                text-align: center;
              }

              .mc-lp-contact-head p {
                margin: 0 0 8px;
                color: #90eae0;
                font-size: 0.76rem;
                font-weight: 800;
                letter-spacing: 0.18em;
                text-transform: uppercase;
              }

              .mc-lp-contact-head h3 {
                margin: 0 0 10px;
                color: #ffffff;
                font-family: 'Fraunces', Georgia, serif;
                font-size: clamp(1.7rem, 3vw, 2.2rem);
                font-weight: 700;
                letter-spacing: -0.03em;
              }

              .mc-lp-contact-head span {
                color: var(--lp-muted);
                font-size: 1rem;
                line-height: 1.7;
              }

              .mc-lp-contact-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 16px;
              }

              .mc-lp-contact-card {
                padding: 24px 22px;
                border-radius: 22px;
                border: 1px solid rgba(148, 163, 184, 0.1);
                background: rgba(8, 14, 24, 0.7);
                text-align: center;
              }

              .mc-lp-contact-card .nm {
                margin: 0 0 6px;
                color: #ffffff;
                font-size: 1.2rem;
                font-weight: 800;
              }

              .mc-lp-contact-card .rl {
                margin: 0 0 18px;
                color: var(--lp-accent);
                font-size: 0.74rem;
                font-weight: 800;
                letter-spacing: 0.16em;
                text-transform: uppercase;
              }

              .mc-lp-btns {
                display: flex;
                justify-content: center;
                flex-wrap: wrap;
                gap: 12px;
              }

              .mc-lp-btns a {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-height: 44px;
                padding: 0 18px;
                border-radius: 14px;
                text-decoration: none !important;
                color: #ffffff !important;
                font-size: 0.86rem;
                font-weight: 800;
                transition: transform 0.2s ease, filter 0.2s ease;
              }

              .mc-lp-btns a:hover {
                transform: translateY(-2px);
                filter: brightness(1.06);
              }

              .mc-lp-wa {
                background: linear-gradient(135deg, #16a34a, #15803d);
                box-shadow: 0 10px 24px rgba(22, 163, 74, 0.28);
              }

              .mc-lp-em {
                background: linear-gradient(135deg, #2563eb, #1d4ed8);
                box-shadow: 0 10px 24px rgba(37, 99, 235, 0.22);
              }

              .mc-lp-cta-wrap {
                padding: 28px 10px 8px;
                text-align: center;
              }

              .mc-lp-cta-wrap p {
                margin: 0 0 6px;
                color: #93e9df;
                font-size: 0.74rem;
                font-weight: 800;
                letter-spacing: 0.18em;
                text-transform: uppercase;
              }

              .mc-lp-cta-wrap h3 {
                margin: 0 0 6px;
                color: #ffffff;
                font-family: 'Fraunces', Georgia, serif;
                font-size: 1.45rem;
                font-weight: 700;
                letter-spacing: -0.03em;
              }

              .mc-lp-cta-wrap span {
                color: var(--lp-muted);
                font-size: 0.94rem;
              }

              @media (max-width: 980px) {
                .mc-lp-hero,
                .mc-lp-two-up,
                .mc-lp-contact-grid {
                  grid-template-columns: 1fr;
                }

                .mc-lp-proof-row,
                .mc-lp-board-foot,
                .mc-lp-stats,
                .mc-lp-mini-grid {
                  grid-template-columns: repeat(2, minmax(0, 1fr));
                }

                .mc-lp-cell-hero,
                .mc-lp-cell-wide,
                .mc-lp-cell-mini {
                  grid-column: span 12;
                }
              }

              @media (max-width: 720px) {
                .mc-lp-inner {
                  padding: 34px 14px 24px;
                }

                .mc-lp-copy,
                .mc-lp-board,
                .mc-lp-panel,
                .mc-lp-contact {
                  padding-left: 18px;
                  padding-right: 18px;
                }

                .mc-lp-h1 {
                  max-width: none;
                  font-size: clamp(2.2rem, 10vw, 3.2rem);
                }

                .mc-lp-proof-row,
                .mc-lp-board-foot,
                .mc-lp-stats,
                .mc-lp-mini-grid {
                  grid-template-columns: 1fr;
                }

                .mc-lp-pill-row {
                  gap: 8px;
                }

                .mc-lp-pill {
                  width: 100%;
                  justify-content: center;
                }

                .mc-lp-flow-card {
                  grid-template-columns: 12px 1fr;
                }

                .mc-lp-flow-tag {
                  display: none;
                }
              }

              </style>
            """
        ),
        dedent(
            """
            <div class="mc-lp">
              <div class="mc-lp-bg"></div>
              <div class="mc-lp-inner">
                <header class="mc-lp-header">
                  <div class="mc-lp-brand">
                    <div class="mc-lp-logo-wrap">__LOGO__</div>
                    <div>
                      <span class="mc-lp-brand-kicker">Plataforma integral</span>
                      <p class="mc-lp-brand-name">MediCare Enterprise PRO</p>
                    </div>
                  </div>
                  <div class="mc-lp-header-badge">Salud domiciliaria · Operación · Auditoría</div>
                </header>

                <section class="mc-lp-hero">
                  <div class="mc-lp-copy">
                    <p class="mc-lp-kicker">Un solo entorno para todo el recorrido del paciente</p>
                    <h1 class="mc-lp-h1">Clínica, coordinación y respaldo legal <em>en una sola plataforma</em></h1>
                    <p class="mc-lp-lead">
                      Ordená visitas, historia clínica, recetas, emergencias, inventario, RRHH y documentación
                      con una experiencia que se ve seria en una demo y responde bien en el día a día.
                    </p>

                    <div class="mc-lp-pill-row">
                      <span class="mc-lp-pill"><strong>Web</strong> celular y escritorio</span>
                      <span class="mc-lp-pill"><strong>Roles</strong> permisos por perfil</span>
                      <span class="mc-lp-pill"><strong>Trazabilidad</strong> auditoría lista</span>
                      <span class="mc-lp-pill"><strong>App paciente</strong> triage y alerta con GPS</span>
                    </div>

                    <div class="mc-lp-proof-row">
                      <div class="mc-lp-proof">
                        <b>Agenda + GPS</b>
                        <span>Fichadas verificables y recorrido operativo más claro.</span>
                      </div>
                      <div class="mc-lp-proof">
                        <b>Historia en vivo</b>
                        <span>Vitales, evolución, estudios y escalas en el mismo flujo.</span>
                      </div>
                      <div class="mc-lp-proof">
                        <b>Respaldo legal</b>
                        <span>PDF, firmas y reportes listos para presentar.</span>
                      </div>
                    </div>
                  </div>

                  <aside class="mc-lp-board">
                    <div class="mc-lp-board-head">
                      <span class="mc-lp-board-kicker">Vista operativa</span>
                      <span class="mc-lp-board-badge">Tiempo real</span>
                    </div>
                    <p class="mc-lp-board-title">Tablero unificado para dirección y terreno</p>

                    <div class="mc-lp-flow">
                      <div class="mc-lp-flow-card">
                        <span class="mc-lp-dot a"></span>
                        <div class="mc-lp-flow-main">
                          <b>Visita con fichada</b>
                          <span>GPS, agenda, llegada, salida y control de tiempo.</span>
                        </div>
                        <span class="mc-lp-flow-tag">Operación</span>
                      </div>

                      <div class="mc-lp-flow-card">
                        <span class="mc-lp-dot b"></span>
                        <div class="mc-lp-flow-main">
                          <b>Historia clínica en vivo</b>
                          <span>Indicaciones, evolución, estudios, escalas y adjuntos.</span>
                        </div>
                        <span class="mc-lp-flow-tag">Clínica</span>
                      </div>

                      <div class="mc-lp-flow-card">
                        <span class="mc-lp-dot c"></span>
                        <div class="mc-lp-flow-main">
                          <b>Cierre documental</b>
                          <span>PDF, consentimientos, recetas y exportes para respaldo.</span>
                        </div>
                        <span class="mc-lp-flow-tag">Legal</span>
                      </div>

                      <div class="mc-lp-flow-card">
                        <span class="mc-lp-dot d"></span>
                        <div class="mc-lp-flow-main">
                          <b>App del paciente</b>
                          <span>Alertas, triage y ubicación para respuesta rápida.</span>
                        </div>
                        <span class="mc-lp-flow-tag">Urgencia</span>
                      </div>
                    </div>

                    <div class="mc-lp-board-foot">
                      <div class="mc-lp-board-mini">
                        <b>Mobile first</b>
                        <span>Funciona bien en celular y también en escritorio.</span>
                      </div>
                      <div class="mc-lp-board-mini">
                        <b>Permisos reales</b>
                        <span>Cada rol ve lo que necesita para trabajar.</span>
                      </div>
                      <div class="mc-lp-board-mini">
                        <b>Listo para demo</b>
                        <span>Se entiende rápido y transmite orden.</span>
                      </div>
                    </div>
                  </aside>
                </section>

                <section class="mc-lp-stats">
                  <div class="mc-lp-stat">
                    <div class="mc-lp-stat-value">1</div>
                    <p class="mc-lp-stat-title">Núcleo operativo</p>
                    <p class="mc-lp-stat-copy">Una sola plataforma para clínica, coordinación, RRHH y documentación.</p>
                  </div>
                  <div class="mc-lp-stat">
                    <div class="mc-lp-stat-value">GPS</div>
                    <p class="mc-lp-stat-title">Fichadas verificables</p>
                    <p class="mc-lp-stat-copy">Llegada y salida con contexto operativo en cada visita.</p>
                  </div>
                  <div class="mc-lp-stat">
                    <div class="mc-lp-stat-value">PDF</div>
                    <p class="mc-lp-stat-title">Respaldo defendible</p>
                    <p class="mc-lp-stat-copy">Reportes, consentimientos y recetas con salida profesional.</p>
                  </div>
                  <div class="mc-lp-stat">
                    <div class="mc-lp-stat-value">Roles</div>
                    <p class="mc-lp-stat-title">Accesos por perfil</p>
                    <p class="mc-lp-stat-copy">Cada usuario entra con permisos alineados a su responsabilidad.</p>
                  </div>
                </section>

                <section class="mc-lp-section-head">
                  <span class="mc-lp-section-kicker">Valor percibido</span>
                  <h2 class="mc-lp-section-title">Una landing más sólida para una plataforma que vende orden</h2>
                  <p class="mc-lp-section-sub">
                    Menos ruido visual y más señales de producto serio: módulos claros, narrativa clínica-operativa y un tono
                    que acompaña reuniones comerciales, demos y presentaciones institucionales.
                  </p>
                </section>
            """
        ),
        dedent(
            """
                <section class="mc-lp-bento">
                  <article class="mc-lp-cell mc-lp-cell-hero">
                    <span class="mc-lp-cell-eyebrow">Coordinación</span>
                    <h4>Dirección con visibilidad y equipo con menos fricción</h4>
                    <p>
                      MediCare centraliza agenda, recursos, pacientes, documentación y seguimiento para que la operación
                      no dependa de planillas, chats sueltos o memoria humana.
                    </p>
                    <div class="mc-lp-cell-list">
                      <div class="mc-lp-cell-item"><strong>Visitas y guardias</strong> con estados, tiempos y contexto.</div>
                      <div class="mc-lp-cell-item"><strong>Profesionales y clínicas</strong> ordenados por empresa y perfil.</div>
                      <div class="mc-lp-cell-item"><strong>Auditoría y cierre</strong> listos para revisión interna o externa.</div>
                    </div>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-wide">
                    <span class="mc-lp-cell-eyebrow">Historia clínica</span>
                    <h4>Registro clínico que se siente contemporáneo</h4>
                    <p>
                      Evolución, escalas, pediatría, estudios y medicación dentro del mismo recorrido. El profesional no
                      cambia de herramienta y la institución conserva una narrativa clínica coherente.
                    </p>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-mini">
                    <span class="mc-lp-cell-eyebrow">Recetas</span>
                    <h4>Firma y documentación</h4>
                    <p>Recetas, consentimientos y PDFs con salida prolija para familia, auditoría o archivo.</p>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-mini">
                    <span class="mc-lp-cell-eyebrow">Emergencias</span>
                    <h4>Respuesta con contexto</h4>
                    <p>Triage, traslado y antecedentes clínicos en un mismo flujo operativo.</p>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-mini">
                    <span class="mc-lp-cell-eyebrow">RRHH</span>
                    <h4>Presentismo y control</h4>
                    <p>Fichajes, tiempos, asistencia y trazabilidad sin sumar herramientas paralelas.</p>
                  </article>
                </section>

                <section class="mc-lp-two-up">
                  <div class="mc-lp-panel">
                    <h3>Cuando la información está dispersa</h3>
                    <p>
                      Aumentan los errores, las demoras y la sensación de improvisación. Centralizar clínica, operación y
                      respaldo legal mejora la imagen del servicio y baja el costo invisible del desorden.
                    </p>
                  </div>

                  <div class="mc-lp-panel">
                    <h3>Lo que cambia con MediCare</h3>
                    <div class="mc-lp-checks">
                      <div class="mc-lp-check">Agenda, visitas y coordinación en tiempo real</div>
                      <div class="mc-lp-check">Historia clínica y documentación en el mismo entorno</div>
                      <div class="mc-lp-check">Fichadas, RRHH y control operativo con menos fricción</div>
                      <div class="mc-lp-check">Exportes y respaldo para auditoría o presentaciones</div>
                    </div>
                  </div>
                </section>

                <section class="mc-lp-mini-grid">
                  <div class="mc-lp-mini-card">
                    <b>Telemedicina</b>
                    <span>Sala por paciente y día, integrada al legajo y al seguimiento clínico.</span>
                  </div>
                  <div class="mc-lp-mini-card">
                    <b>Pediatría</b>
                    <span>Curvas, controles y evolución ordenada para seguimiento continuo.</span>
                  </div>
                  <div class="mc-lp-mini-card">
                    <b>Caja e inventario</b>
                    <span>Prácticas, estados, materiales y movimientos en el mismo ecosistema.</span>
                  </div>
                  <div class="mc-lp-mini-card">
                    <b>Red profesional</b>
                    <span>Instituciones, profesionales y empresas conectadas en un solo directorio.</span>
                  </div>
                </section>
            """
        ),
        dedent(
            """
                <section class="mc-lp-contact">
                  <div class="mc-lp-contact-head">
                    <p>Implementación y soporte</p>
                    <h3>Contacto directo con el equipo</h3>
                    <span>Listo para reuniones comerciales, demos guiadas e implementación operativa.</span>
                  </div>

                  <div class="mc-lp-contact-grid">
                    <div class="mc-lp-contact-card">
                      <p class="nm">Enzo N. Girardi</p>
                      <p class="rl">Desarrollo y soporte</p>
                      <div class="mc-lp-btns">
                        <a class="mc-lp-wa" href="https://wa.me/5493584302024" target="_blank" rel="noopener">WhatsApp</a>
                        <a class="mc-lp-em" href="mailto:enzogirardi84@gmail.com">Email</a>
                      </div>
                    </div>

                    <div class="mc-lp-contact-card">
                      <p class="nm">Dario Lanfranco</p>
                      <p class="rl">Implementación y contratos</p>
                      <div class="mc-lp-btns">
                        <a class="mc-lp-wa" href="https://wa.me/5493584201263" target="_blank" rel="noopener">WhatsApp</a>
                        <a class="mc-lp-em" href="mailto:dariolanfrancoruffener@gmail.com">Email</a>
                      </div>
                    </div>
                  </div>
                </section>

                <div class="mc-lp-cta-wrap">
                  <p>Acceso al sistema</p>
                  <h3>Ingresá a la demo operativa</h3>
                  <span>Explorá módulos, roles y documentos en vivo.</span>
                </div>
              </div>
            </div>
            """
        ),
    ]
    return "".join(parts).replace("__LOGO__", logo_html)
