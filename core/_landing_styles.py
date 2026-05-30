"""CSS de la landing pre-login (extraido de _landing_html_parts.py)."""

_PART_1 = """
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,600;0,9..144,700;0,9..144,800;1,9..144,600&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" media="print" onload="this.media='all'">
            <noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,600;0,9..144,700;0,9..144,800;1,9..144,600&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap"></noscript>
            <style>

              :root {
                --lp-void: #050812;
                --lp-accent-glow: 0 0 40px rgba(45, 212, 191, 0.15);
                --lp-panel: rgba(11, 18, 31, 0.88);
                --lp-panel-soft: rgba(15, 24, 40, 0.78);
                --lp-panel-strong: rgba(17, 28, 47, 0.96);
                --lp-line: rgba(125, 211, 252, 0.18);
                --lp-line-strong: rgba(45, 212, 191, 0.32);
                --lp-text: #f4f7fb;
                --lp-muted: #94a3b8;
                --lp-accent: #2dd4bf;
                --lp-blue: #60a5fa;
                --lp-gold: #fbbf24;
                --lp-shadow: 0 28px 80px rgba(0, 0, 0, 0.38);
                --lp-inset: inset 0 1px 0 rgba(255, 255, 255, 0.045);
                --lp-radius-xl: 28px;
                --lp-sheen: linear-gradient(105deg, rgba(255,255,255,0.07) 0%, transparent 42%, transparent 58%, rgba(255,255,255,0.04) 100%);
              }

              .mc-lp {
                position: relative;
                isolation: isolate;
                overflow-x: clip;
                color: var(--lp-text);
                font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
                -webkit-font-smoothing: antialiased;
                -moz-osx-font-smoothing: grayscale;
                text-rendering: optimizeLegibility;
              }

              .mc-lp * {
                box-sizing: border-box;
              }

              .mc-lp-bg {
                position: fixed;
                inset: 0;
                z-index: -2;
                background:
                  radial-gradient(ellipse 90% 55% at 50% -12%, rgba(45, 212, 191, 0.09), transparent 55%),
                  radial-gradient(circle at 14% 18%, rgba(45, 212, 191, 0.14), transparent 28%),
                  radial-gradient(circle at 88% 8%, rgba(96, 165, 250, 0.14), transparent 32%),
                  radial-gradient(circle at 72% 92%, rgba(56, 189, 248, 0.06), transparent 40%),
                  linear-gradient(168deg, #03050a 0%, #060d18 38%, #0a1524 100%);
              }

              .mc-lp-bg::before {
                content: "";
                position: absolute;
                inset: 0;
                opacity: 0.55;
                background:
                  radial-gradient(ellipse 120% 80% at 20% 60%, rgba(37, 99, 235, 0.07), transparent 50%),
                  radial-gradient(ellipse 100% 70% at 80% 40%, rgba(13, 148, 136, 0.06), transparent 48%);
                pointer-events: none;
              }

              .mc-lp-bg::after {
                content: "";
                position: absolute;
                inset: 0;
                opacity: 0.38;
                background-image:
                  linear-gradient(rgba(148, 163, 184, 0.038) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(148, 163, 184, 0.038) 1px, transparent 1px),
                  radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.028) 1px, transparent 0);
                background-size: 48px 48px, 48px 48px, 16px 16px;
                mask-image: radial-gradient(circle at 48% 36%, black 0%, rgba(0, 0, 0, 0.9) 45%, transparent 92%);
                pointer-events: none;
              }

              .mc-lp-noise {
                position: fixed;
                inset: 0;
                z-index: -1;
                opacity: 0.035;
                pointer-events: none;
                mix-blend-mode: overlay;
                background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='a'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.78' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23a)'/%3E%3C/svg%3E");
                background-size: 220px 220px;
              }

              .mc-lp-inner {
                max-width: 1100px;
                margin: 0 auto;
                padding: 24px clamp(16px, 3vw, 24px) 28px;
              }

              .mc-lp-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 14px;
                flex-wrap: wrap;
                margin-bottom: 20px;
                padding-bottom: 16px;
                border-bottom: 1px solid rgba(148, 163, 184, 0.1);
              }

              .mc-lp-brand {
                display: flex;
                align-items: center;
                gap: 18px;
              }

              .mc-lp-logo-wrap {
                padding: 16px 18px;
                border-radius: 24px;
                background: linear-gradient(180deg, rgba(255, 255, 255, 0.99), rgba(241, 245, 249, 0.94));
                box-shadow:
                  0 20px 55px rgba(0, 0, 0, 0.36),
                  0 0 0 1px rgba(255, 255, 255, 0.5) inset,
                  0 0 0 1px rgba(45, 212, 191, 0.12);
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

              .mc-lp-trust {
                margin: -8px 0 18px;
                padding: 10px 14px;
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.12);
                background: linear-gradient(180deg, rgba(8, 14, 26, 0.75), rgba(5, 10, 18, 0.82));
                box-shadow: var(--lp-inset), 0 12px 40px rgba(0, 0, 0, 0.18);
                backdrop-filter: blur(14px);
              }

              .mc-lp-trust-inner {
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                justify-content: center;
                gap: 8px 10px;
              }

              .mc-lp-trust-item {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 6px 14px;
                border-radius: 999px;
                font-size: 0.72rem;
                font-weight: 700;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                color: #b8c9dc;
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(148, 163, 184, 0.1);
              }

              .mc-lp-trust-item::before {
                content: "";
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: var(--lp-accent);
                box-shadow: 0 0 10px rgba(45, 212, 191, 0.65);
                flex-shrink: 0;
              }

              .mc-lp-hero {
                display: grid;
                grid-template-columns: minmax(0, 1.12fr) minmax(300px, 0.88fr);
                gap: 16px;
                align-items: stretch;
                margin-bottom: 20px;
              }

              .mc-lp-copy {
                position: relative;
                padding: 24px 24px 22px;
                border-radius: 24px;
                background:
                  var(--lp-sheen),
                  linear-gradient(165deg, rgba(10, 16, 28, 0.94) 0%, rgba(6, 11, 20, 0.9) 100%),
                  radial-gradient(circle at 12% 8%, rgba(45, 212, 191, 0.1), transparent 42%);
                border: 1px solid rgba(148, 163, 184, 0.14);
                box-shadow: var(--lp-shadow), var(--lp-inset);
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
                margin: 0 0 12px;
                max-width: 22ch;
                color: #ffffff;
                font-family: 'Fraunces', Georgia, serif;
                font-size: clamp(1.8rem, 3.6vw, 2.8rem);
                font-weight: 800;
                line-height: 1.08;
                letter-spacing: -0.04em;
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
                margin: 0 0 16px;
                max-width: 38rem;
                color: #a8b8cc;
                font-size: 0.92rem;
                line-height: 1.6;
                font-weight: 500;
              }

              .mc-lp-hero-badge {
                display: inline-block;
                margin: 0 0 14px;
                padding: 7px 16px;
                border-radius: 999px;
                font-size: 0.7rem;
                font-weight: 800;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: #0f172a;
                background: linear-gradient(135deg, #fef08a, #fbbf24);
                border: 1px solid rgba(251, 191, 36, 0.55);
                box-shadow: 0 8px 22px rgba(251, 191, 36, 0.15);
              }

              .mc-lp-cta-group {
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
                margin-bottom: 22px;
              }

              .mc-lp-cta-group a {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-height: 46px;
                padding: 0 22px;
                border-radius: 14px;
                font-size: 0.88rem;
                font-weight: 800;
                text-decoration: none !important;
                transition: transform 0.2s ease, filter 0.2s ease, border-color 0.2s ease;
              }

              .mc-lp-cta-group a:focus-visible {
                outline: 3px solid #5eead4;
                outline-offset: 3px;
              }

              .mc-lp-btn-primary {
                background: linear-gradient(135deg, #14b8a6, #2563eb);
                color: #fff !important;
                box-shadow: 0 12px 30px rgba(37, 99, 235, 0.28);
              }

              .mc-lp-btn-primary:hover {
                transform: translateY(-2px);
                filter: brightness(1.06);
              }

              .mc-lp-btn-outline {
                border: 1px solid rgba(148, 163, 184, 0.38);
                background: rgba(8, 13, 23, 0.6);
                color: #e2e8f0 !important;
              }

              .mc-lp-btn-outline:hover {
                transform: translateY(-2px);
                border-color: var(--lp-accent);
                color: #fff !important;
              }

              #mc-lp-modulos,
              #mc-lp-contact {
                scroll-margin-top: 20px;
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
                padding: 16px 16px 14px;
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.1);
                background: rgba(10, 16, 29, 0.82);
                box-shadow: var(--lp-inset);
                backdrop-filter: blur(10px);
                min-height: 92px;
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
                padding: 18px 18px 18px;
                border-radius: 24px;
                background:
                  var(--lp-sheen),
                  linear-gradient(168deg, rgba(13, 21, 36, 0.98) 0%, rgba(6, 10, 18, 0.99) 100%),
                  radial-gradient(circle at 92% 6%, rgba(45, 212, 191, 0.08), transparent 36%);
                border: 1px solid rgba(96, 165, 250, 0.18);
                box-shadow: var(--lp-shadow), var(--lp-inset), 0 0 80px rgba(37, 99, 235, 0.06);
                overflow: hidden;
              }

              .mc-lp-board-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 14px;
                flex-wrap: wrap;
                margin-bottom: 16px;
              }

              .mc-lp-status-indicator {
                display: inline-flex;
                align-items: center;
                gap: 10px;
                min-height: 34px;
                padding: 0 14px 0 12px;
                border-radius: 999px;
                background: rgba(45, 212, 191, 0.14);
                color: #99f6e4;
                font-size: 0.72rem;
                font-weight: 800;
                letter-spacing: 0.12em;
                text-transform: uppercase;
              }

              .mc-lp-status-indicator::before {
                content: "";
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: var(--lp-accent);
                box-shadow: 0 0 12px rgba(45, 212, 191, 0.85);
                flex-shrink: 0;
              }

              .mc-lp-board-side-label {
                color: #c9d7e8;
                font-size: 0.82rem;
                font-weight: 800;
                letter-spacing: 0.14em;
                text-transform: uppercase;
              }

              .mc-lp-board-title {
                margin: 0 0 20px;
                color: #f1f5f9;
                font-family: 'Fraunces', Georgia, serif;
                font-size: clamp(1.28rem, 2.2vw, 1.48rem);
                font-weight: 700;
                letter-spacing: -0.03em;
                line-height: 1.25;
                max-width: 20em;
              }
            """



_PART_2 = """
              .mc-lp-flow {
                display: flex;
                flex-direction: column;
                gap: 12px;
              }

              .mc-lp-flow-card {
                display: grid;
                grid-template-columns: 44px 1fr auto;
                gap: 14px;
                align-items: start;
                padding: 16px 16px 16px 14px;
                border-radius: 18px;
                border: 1px solid rgba(148, 163, 184, 0.11);
                background: rgba(16, 24, 40, 0.9);
                box-shadow: var(--lp-inset);
                transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
              }

              .mc-lp-flow-card-active {
                border-color: rgba(45, 212, 191, 0.42);
                box-shadow: 0 0 0 1px rgba(45, 212, 191, 0.18), 0 12px 32px rgba(0, 0, 0, 0.2);
              }

              .mc-lp-flow-icon {
                width: 42px;
                height: 42px;
                border-radius: 14px;
                flex-shrink: 0;
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(148, 163, 184, 0.12);
              }

              .mc-lp-flow-icon-op {
                background: linear-gradient(145deg, rgba(45, 212, 191, 0.35), rgba(13, 148, 136, 0.25));
                border-color: rgba(45, 212, 191, 0.35);
                box-shadow: 0 0 20px rgba(45, 212, 191, 0.2);
              }

              .mc-lp-flow-icon-cli {
                background: linear-gradient(145deg, rgba(96, 165, 250, 0.35), rgba(37, 99, 235, 0.22));
                border-color: rgba(96, 165, 250, 0.35);
                box-shadow: 0 0 18px rgba(59, 130, 246, 0.18);
              }

              .mc-lp-flow-icon-leg {
                background: linear-gradient(145deg, rgba(251, 191, 36, 0.3), rgba(217, 119, 6, 0.2));
                border-color: rgba(251, 191, 36, 0.35);
              }

              .mc-lp-flow-icon-urg {
                background: linear-gradient(145deg, rgba(251, 113, 133, 0.32), rgba(225, 29, 72, 0.2));
                border-color: rgba(251, 113, 133, 0.35);
                box-shadow: 0 0 16px rgba(251, 113, 133, 0.15);
              }

              .mc-lp-flow-body b {
                display: block;
                margin-bottom: 4px;
                color: #ffffff;
                font-size: 0.95rem;
                font-weight: 800;
              }

              .mc-lp-flow-body p {
                margin: 0;
                color: var(--lp-muted);
                font-size: 0.81rem;
                line-height: 1.5;
              }

              .mc-lp-flow-tag {
                display: inline-flex;
                align-items: center;
                align-self: center;
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

              .mc-lp-board-footer {
                margin-top: 10px;
                padding: 10px 14px;
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.1);
                background: rgba(8, 13, 23, 0.65);
                text-align: center;
              }

              .mc-lp-board-footer span {
                color: var(--lp-muted);
                font-size: 0.8rem;
                font-weight: 600;
                line-height: 1.5;
              }

              .mc-lp-board-footer strong {
                color: #a5f3fc;
                font-weight: 800;
              }

              .mc-lp-stats {
                margin: 0 0 28px;
              }

              .mc-lp-stats-head {
                text-align: center;
                max-width: 42rem;
                margin: 0 auto 14px;
                padding: 0 8px;
              }

              .mc-lp-stats-h2 {
                margin: 0;
                font-family: 'Fraunces', Georgia, serif;
                font-size: clamp(1.15rem, 2.8vw, 1.45rem);
                font-weight: 700;
                letter-spacing: -0.03em;
                line-height: 1.25;
                color: #e8f0fa;
              }

              .mc-lp-stat-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 16px;
              }

              .mc-lp-stat-item {
                position: relative;
                display: flex;
                gap: 12px;
                align-items: flex-start;
                padding: 16px 16px 14px;
                min-height: 90px;
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.11);
                background: var(--lp-panel-soft);
                box-shadow: 0 16px 44px rgba(0, 0, 0, 0.2), var(--lp-inset);
                overflow: hidden;
              }

              .mc-lp-stat-item::before {
                content: "";
                position: absolute;
                left: 20px;
                right: 20px;
                top: 0;
                height: 2px;
                border-radius: 999px;
                background: linear-gradient(90deg, var(--lp-accent), var(--lp-blue));
              }

              .mc-lp-stat-num {
                flex-shrink: 0;
                min-width: 3.2rem;
                color: #ffffff;
                font-family: 'Fraunces', Georgia, serif;
                font-size: 1.85rem;
                font-weight: 700;
                letter-spacing: -0.04em;
                line-height: 1;
              }

              .mc-lp-stat-body {
                min-width: 0;
              }

              .mc-lp-stat-body h3 {
                margin: 0 0 6px;
                color: #edf5fd;
                font-size: 0.92rem;
                font-weight: 800;
                letter-spacing: -0.02em;
              }

              .mc-lp-stat-body p {
                margin: 0;
                color: var(--lp-muted);
                font-size: 0.8rem;
                line-height: 1.55;
              }

              .mc-lp-section-head {
                margin-bottom: 16px;
                padding-bottom: 4px;
              }

              .mc-lp-section-kicker {
                display: inline-block;
                margin-bottom: 12px;
                color: #7ee0d4;
                font-size: 0.72rem;
                font-weight: 800;
                letter-spacing: 0.2em;
                text-transform: uppercase;
              }

              .mc-lp-section-title {
                margin: 0 0 14px;
                color: #ffffff;
                font-family: 'Fraunces', Georgia, serif;
                font-size: clamp(1.55rem, 2.8vw, 1.95rem);
                font-weight: 700;
                letter-spacing: -0.03em;
                line-height: 1.2;
                max-width: 36rem;
              }

              .mc-lp-section-sub {
                margin: 0;
                max-width: 44rem;
                color: var(--lp-muted);
                font-size: 0.98rem;
                line-height: 1.72;
              }
            """



_PART_3 = """
              .mc-lp-bento {
                display: grid;
                grid-template-columns: repeat(12, minmax(0, 1fr));
                gap: 12px;
                margin-bottom: 28px;
              }

              .mc-lp-cell {
                height: 100%;
                padding: 18px 18px;
                border-radius: 18px;
                border: 1px solid rgba(148, 163, 184, 0.13);
                background:
                  var(--lp-sheen),
                  var(--lp-panel);
                box-shadow: 0 20px 48px rgba(0, 0, 0, 0.2), var(--lp-inset);
                transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
              }

              .mc-lp-cell:hover {
                transform: translateY(-2px);
                border-color: rgba(45, 212, 191, 0.22);
                box-shadow: 0 24px 56px rgba(0, 0, 0, 0.24), var(--lp-inset);
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

              .mc-lp-cell h3 {
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
                padding: 13px 16px 13px 14px;
                border-radius: 14px;
                border: 1px solid rgba(148, 163, 184, 0.09);
                border-left: 3px solid rgba(45, 212, 191, 0.45);
                background: rgba(7, 12, 22, 0.72);
                color: #d8e4f2;
                font-size: 0.85rem;
                font-weight: 600;
                line-height: 1.45;
              }

              .mc-lp-cell-item strong {
                color: #ffffff;
              }

              .mc-lp-two-up {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 12px;
                margin-bottom: 24px;
              }

              .mc-lp-panel {
                padding: 20px 20px;
                border-radius: 18px;
                border: 1px solid rgba(148, 163, 184, 0.11);
                background: linear-gradient(180deg, rgba(14, 22, 36, 0.94), rgba(9, 15, 24, 0.9));
                box-shadow: 0 22px 52px rgba(0, 0, 0, 0.22), var(--lp-inset);
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
                content: "âœ“";
                margin-right: 10px;
                color: var(--lp-accent);
                font-weight: 900;
              }

              .mc-lp-mini-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 10px;
                margin-bottom: 24px;
              }

              .mc-lp-mini-card {
                padding: 14px 14px;
                border-radius: 14px;
                border: 1px solid rgba(148, 163, 184, 0.1);
                background: rgba(8, 13, 23, 0.72);
                box-shadow: var(--lp-inset);
                transition: transform 0.2s ease, border-color 0.2s ease;
              }

              .mc-lp-mini-card:hover {
                transform: translateY(-2px);
                border-color: rgba(45, 212, 191, 0.28);
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



_PART_4 = """
              .mc-lp-contact {
                position: relative;
                overflow: hidden;
                padding: 28px 24px 24px;
                border-radius: 24px;
                border: 1px solid rgba(45, 212, 191, 0.26);
                background:
                  var(--lp-sheen),
                  linear-gradient(180deg, rgba(11, 18, 31, 0.97), rgba(6, 10, 18, 0.99)),
                  radial-gradient(circle at top right, rgba(45, 212, 191, 0.1), transparent 30%);
                box-shadow: var(--lp-shadow), var(--lp-inset), 0 0 100px rgba(45, 212, 191, 0.04);
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

              .mc-lp-incident {
                margin: 12px auto 0;
                max-width: 680px;
                padding: 12px 16px;
                border-radius: 16px;
                border: 1px solid rgba(251, 191, 36, 0.28);
                background: linear-gradient(180deg, rgba(74, 33, 6, 0.5), rgba(49, 22, 4, 0.42));
                text-align: center;
              }

              .mc-lp-incident p {
                margin: 0 0 14px;
                color: #fde68a;
                font-size: 0.9rem;
                font-weight: 600;
                line-height: 1.6;
              }

              .mc-lp-su {
                background: linear-gradient(135deg, #ca8a04, #a16207);
                box-shadow: 0 10px 24px rgba(202, 138, 4, 0.24);
              }

              .mc-lp-cta-wrap {
                padding: 16px 10px 4px;
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

              .mc-lp-tagline {
                margin: 0 auto 4px;
                max-width: 640px;
                padding: 12px 16px;
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.1);
                background: rgba(6, 11, 20, 0.55);
                text-align: center;
                color: #8b9cb3;
                font-size: 0.82rem;
                font-weight: 600;
                line-height: 1.65;
                letter-spacing: 0.02em;
              }

              .mc-lp-tagline strong {
                color: #c5d4e8;
                font-weight: 800;
              }

              .mc-lp-product-access {
                margin: 14px auto 18px;
                max-width: 900px;
                display: grid;
                grid-template-columns: minmax(0, 1fr) auto;
                gap: 14px;
                align-items: center;
                padding: 16px 18px;
                border-radius: 18px;
                border: 1px solid rgba(45, 212, 191, 0.26);
                background:
                  var(--lp-sheen),
                  radial-gradient(ellipse 70% 90% at 100% 0%, rgba(45, 212, 191, 0.12), transparent 58%),
                  linear-gradient(145deg, rgba(17, 28, 47, 0.96), rgba(6, 11, 20, 0.94));
                box-shadow: var(--lp-shadow), var(--lp-inset);
              }

              .mc-lp-product-access p {
                margin: 0 0 7px;
                color: var(--lp-accent);
                font-size: 0.72rem;
                font-weight: 800;
                letter-spacing: 0.18em;
                text-transform: uppercase;
              }

              .mc-lp-product-access h3 {
                margin: 0 0 8px;
                color: #ffffff;
                font-family: 'Fraunces', Georgia, serif;
                font-size: clamp(1.35rem, 2.2vw, 1.85rem);
                letter-spacing: -0.03em;
              }

              .mc-lp-product-access span {
                display: block;
                max-width: 48rem;
                color: #a8b8cc;
                font-size: 0.94rem;
                line-height: 1.65;
              }

              .mc-lp-product-link {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-height: 52px;
                padding: 0 24px;
                border-radius: 14px;
                background: linear-gradient(135deg, #14b8a6, #2563eb);
                color: #ffffff !important;
                font-size: 0.84rem;
                font-weight: 900;
                letter-spacing: 0.1em;
                text-decoration: none !important;
                text-transform: uppercase;
                white-space: nowrap;
                box-shadow: 0 12px 30px rgba(37, 99, 235, 0.26);
              }

              .mc-lp-product-link:hover {
                transform: translateY(-2px);
                filter: brightness(1.06);
              }

              @media (prefers-reduced-motion: reduce) {
                .mc-lp-cell,
                .mc-lp-mini-card,
                .mc-lp-btns a,
                .mc-lp-cta-group a {
                  transition: none !important;
                }
                .mc-lp-cell:hover,
                .mc-lp-mini-card:hover,
                .mc-lp-btns a:hover,
                .mc-lp-cta-group a:hover {
                  transform: none !important;
                }
              }

              @media (max-width: 980px) {
                .mc-lp-hero,
                .mc-lp-two-up,
                .mc-lp-contact-grid {
                  grid-template-columns: 1fr;
                }

                .mc-lp-product-access {
                  grid-template-columns: 1fr;
                }

                .mc-lp-proof-row,
                .mc-lp-stat-grid,
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
                  padding: 20px 12px 16px;
                }

                .mc-lp-header {
                  margin-bottom: 14px;
                  padding-bottom: 12px;
                }

                .mc-lp-trust {
                  margin-bottom: 18px;
                  padding: 8px 10px;
                }

                .mc-lp-copy {
                  padding: 16px 16px 18px;
                }

                .mc-lp-board {
                  padding: 14px 14px;
                }

                .mc-lp-panel {
                  padding: 14px 14px;
                }

                .mc-lp-contact {
                  padding: 18px 16px 20px;
                }

                .mc-lp-h1 {
                  max-width: none;
                  font-size: clamp(1.55rem, 7vw, 2.2rem);
                }

                .mc-lp-lead {
                  font-size: 0.86rem;
                }

                .mc-lp-proof-row,
                .mc-lp-stat-grid,
                .mc-lp-mini-grid {
                  grid-template-columns: 1fr;
                }

                .mc-lp-stat-item {
                  padding: 12px 14px;
                  min-height: 76px;
                }

                .mc-lp-cell {
                  padding: 14px 14px;
                }

                .mc-lp-pill-row {
                  gap: 6px;
                }

                .mc-lp-pill {
                  width: 100%;
                  justify-content: center;
                  font-size: 0.76rem;
                }

                .mc-lp-product-link {
                  width: 100%;
                }

                .mc-lp-flow-card {
                  grid-template-columns: 44px 1fr;
                  padding: 12px 12px;
                }

                .mc-lp-flow-tag {
                  display: none;
                }

                .mc-lp-faq summary {
                  font-size: 0.84rem;
                  min-height: 38px;
                  padding: 8px 12px;
                }
                .mc-lp-faq details > div {
                  font-size: 0.82rem;
                  padding: 0 12px 10px;
                }
              }

              /* â”€â”€ Secciones aparecen con fade-in (CSS puro, sin JS) â”€â”€ */
              .mc-lp-fade {
                animation: mcFadeUp 0.7s ease both;
              }
              @keyframes mcFadeUp {
                from { opacity: 0; transform: translateY(18px); }
                to   { opacity: 1; transform: translateY(0); }
              }
              @media (prefers-reduced-motion: reduce) {
                .mc-lp-fade { animation: none; opacity: 1; transform: none; }
              }

              /* â”€â”€ FAQ accordion â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
              .mc-lp-faq { margin-bottom: 24px; }
              .mc-lp-faq details {
                margin-bottom: 4px;
                border-radius: 12px;
                border: 1px solid rgba(148, 163, 184, 0.1);
                background: rgba(10, 16, 29, 0.7);
              }
              .mc-lp-faq details[open] { border-color: rgba(45, 212, 191, 0.3); }
              .mc-lp-faq summary {
                display: flex;
                align-items: center;
                justify-content: space-between;
                min-height: 42px;
                padding: 10px 14px;
                color: #e8f0fa;
                font-size: 0.88rem;
                font-weight: 700;
                cursor: pointer;
                list-style: none;
              }
              .mc-lp-faq summary::-webkit-details-marker { display: none; }
              .mc-lp-faq summary::after {
                content: "+";
                font-size: 1.1rem;
                color: var(--lp-accent);
              }
              .mc-lp-faq details[open] summary::after { content: "âˆ’"; }
              .mc-lp-faq details > div {
                padding: 0 14px 12px;
                color: #a8b8cc;
                font-size: 0.85rem;
                line-height: 1.6;
              }

              /* â”€â”€ SVG icon decorativos en cards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
              .mc-lp-cell-icon {
                display: flex;
                align-items: center;
                justify-content: center;
                width: 48px;
                height: 48px;
                margin-bottom: 14px;
                border-radius: 16px;
                background: rgba(45, 212, 191, 0.1);
                border: 1px solid rgba(45, 212, 191, 0.2);
                box-shadow: 0 0 20px rgba(45, 212, 191, 0.08);
              }
              .mc-lp-cell-icon-hero {
                background: rgba(45, 212, 191, 0.15);
                border-color: rgba(45, 212, 191, 0.35);
                box-shadow: 0 0 30px rgba(45, 212, 191, 0.12);
              }
              .mc-lp-cell-icon svg {
                width: 26px;
                height: 26px;
                fill: none;
                stroke: var(--lp-accent);
                stroke-width: 2;
                stroke-linecap: round;
                stroke-linejoin: round;
              }

              </style>
            """





