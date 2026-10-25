# 3D-Model

3D animation work, made entirely from code: Blender (bpy) + HTML UI + synthesized sound + ffmpeg.

## Stack
- Blender 5.2 as Python module (`pip install bpy`, needs Python 3.13), Cycles
- Playwright + Chromium (UI texture per frame), numpy/scipy/pedalboard (sound), ffmpeg

## Run
- Setup once: `bash .claude/skills/code-film/scripts/setup.sh` (venv at /opt/b3d)
- New film: `bash .claude/skills/code-film/scripts/new_film.sh films/<name>`
- Build: `PY=/opt/b3d/bin/python films/<name>/film.sh preview|draft|final`

## Structure
- `.claude/skills/code-film/`: the skill (SKILL.md = method + rules), `template/` = working 9 s demo film
- `.claude/skills/caveman|ultracave|megacave/`: terse-reply skill, copied from JuliusBrussee/caveman v4.0.1 (Apache-2.0); SKILL.md only, no plugin hooks
- `.claude/skills/graphify/`: codebase knowledge-graph skill, copied from safishamsi/graphify 0.9.95 (SKILL.md + references/); manual only (`disable-model-invocation`, run with /graphify); needs `pip install graphifyy` (skill self-installs). Uses Gemini only if GEMINI_API_KEY/GOOGLE_API_KEY set, else Claude subagents
- `.claude/skills/ui-ux-pro-max/`: UI/UX design data + search.py (stdlib only), from nextlevelbuilder/ui-ux-pro-max-skill @d14efff (MIT); plugin paths replaced with `<skill-dir>`; tests dropped
- `films/`: per-film working dirs (gitignored)

## Decisions
- Method learned from Nate Herk reel (instagram DeuZ4BnhCqA): timeline.py drives UI, 3D, sound
- Cycles CPU, not EEVEE, when no GPU: EEVEE on software GL ~50 s/frame vs ~6 s Cycles
- Positions measured from DOM (layout.json), never typed; times in beats
- QA gate (check.py) must pass before encode: framing, speed, camera pops, audio sync, black frames
- Area lights `visible_glossy=False` (hard white reflections on glossy UI)
- `-pix_fmt yuv420p` always (yuv444 from PNG won't play on phones)

## Preferences
- User wants a working, repeatedly tested skill, not a one-off
- Never use OpenAI/Codex or other external AI services without asking (Higgsfield also counts)

## Open tasks
- [ ] Final 1080p render on a GPU machine (CPU here: ~hours)
- [ ] Untested: `BLENDER=/path/to/blender film.sh` path (no Blender binary in this container)
