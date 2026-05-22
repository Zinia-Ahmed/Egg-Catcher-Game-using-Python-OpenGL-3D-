"""
╔══════════════════════════════════════════════════════════════════╗
║     🐣  CHICKEN EGG CATCHER 3D  —  ULTRA EDITION  🐣           ║
║  Controls: ← → Arrow Keys | SPACE = Pause | R = Restart        ║
║  Catch eggs from ducks above, avoid bombs, grab power-ups!     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import matplotlib
matplotlib.use('TkAgg') 
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.transforms as transforms
from matplotlib.patches import FancyBboxPatch, Circle, Ellipse, FancyArrowPatch, Wedge
from matplotlib.collections import PatchCollection
import matplotlib.animation as animation
from matplotlib.colors import to_rgba
import matplotlib.patheffects as pe
import random, math, time, sys

# ─── GAME CONSTANTS ────────────────────────────────────────────────
W, H = 14, 10        
BASKET_W = 1.4
BASKET_SPEED = 0.45
EGG_RADIUS = 0.18
DUCK_Y = 8.2
GROUND_Y = 0.55
FPS = 50
LANE_XS = [-5, -2.5, 0, 2.5, 5]   


EGG_TYPES = {
    'normal': dict(color='#fffde7', outline='#f9a825', pts=1,  prob=55, label='Normal'),
    'golden': dict(color='#FFD700', outline='#FF8C00', pts=5,  prob=18, label='Golden ✨'),
    'bomb':   dict(color='#222222', outline='#ff1744', pts=-3, prob=12, label='💣 BOMB'),
    'freeze': dict(color='#80d8ff', outline='#0091ea', pts=2,  prob=8,  label='❄ Freeze'),
    'multi':  dict(color='#e040fb', outline='#aa00ff', pts=3,  prob=7,  label='🔮 Multi'),
}

POWERUP_TYPES = {
    'shield':    dict(color='#69f0ae', label='🛡 SHIELD', duration=8),
    'magnet':    dict(color='#ff80ab', label='🧲 MAGNET', duration=6),
    'slow':      dict(color='#80d8ff', label='⏱ SLOW',   duration=7),
    'doublepts': dict(color='#ffd740', label='2× PTS',   duration=10),
}

# ─── STATE ─────────────────────────────────────────────────────────
state = {}

def reset_game():
    global state
    state = dict(
        score=0, lives=3, level=1, combo=0, max_combo=0,
        basket_x=0.0,
        eggs=[],
        particles=[],
        powerups=[],
        active_powerups={},          
        duck_wobble=[0]*5,
        duck_dir=[1]*5,
        egg_timer=0,
        egg_interval=90,
        freeze_timer=0,
        paused=False,
        game_over=False,
        messages=[],                 
        bg_hue=0.0,
        streak_flash=0,
        total_eggs_caught=0,
        t=0,
        input_basket_dx=0,
        key_left=False, key_right=False,
        spawn_rain=False,
        rain_timer=0,
        # per-duck color cycle
        duck_colors=[
            ('#ff6b6b','#ffa07a'),
            ('#ffe66d','#f7b733'),
            ('#a8ff78','#78ffd6'),
            ('#a18cd1','#fbc2eb'),
            ('#f093fb','#f5576c'),
        ]
    )

reset_game()

# ─── FIGURE SETUP ──────────────────────────────────────────────────
fig = plt.figure(figsize=(14, 10), facecolor='#0a0a1a')
fig.canvas.manager.set_window_title("🐣 Chicken Egg Catcher 3D — Ultra Edition")

ax = fig.add_axes([0, 0, 1, 1])
ax.set_facecolor('#0a0a1a')
ax.set_xlim(-W/2, W/2)
ax.set_ylim(0, H)
ax.set_aspect('equal')
ax.axis('off')

# ─── DRAWING HELPERS ───────────────────────────────────────────────

def lerp_color(c1, c2, t):
    r1,g1,b1,_ = to_rgba(c1)
    r2,g2,b2,_ = to_rgba(c2)
    t = max(0, min(1, t))
    return (r1+(r2-r1)*t, g1+(g2-g1)*t, b1+(b2-b1)*t, 1)

def hex_alpha(hex_col, alpha):
    r,g,b,_ = to_rgba(hex_col)
    return (r,g,b,alpha)

# ─── EGG SPAWN ─────────────────────────────────────────────────────

def spawn_egg():
    lane = random.randint(0, 4)
    x = LANE_XS[lane] + random.uniform(-0.3, 0.3)
    # pick type with weighted probability
    types = list(EGG_TYPES.keys())
    weights = [EGG_TYPES[t]['prob'] for t in types]
    etype = random.choices(types, weights=weights, k=1)[0]
    speed_base = 0.055 + state['level'] * 0.008
    speed = speed_base + random.uniform(-0.01, 0.02)
    state['eggs'].append(dict(
        x=x, y=DUCK_Y-0.4, etype=etype,
        speed=speed, lane=lane,
        spin=random.uniform(-3, 3),
        angle=0.0,
        shadow_alpha=0.0,
        state='falling',   # falling / caught / missed / explode
        explode_t=0,
    ))

def spawn_powerup():
    x = random.uniform(-5.5, 5.5)
    ptype = random.choice(list(POWERUP_TYPES.keys()))
    state['powerups'].append(dict(x=x, y=DUCK_Y-0.3, ptype=ptype, speed=0.038, angle=0.0))

# ─── PARTICLES ─────────────────────────────────────────────────────

def emit_particles(x, y, color, n=18, style='burst'):
    for _ in range(n):
        angle = random.uniform(0, 2*math.pi)
        speed = random.uniform(0.03, 0.18) if style=='burst' else random.uniform(0.01,0.1)
        size  = random.uniform(4, 14)
        life  = random.randint(15, 35)
        state['particles'].append(dict(
            x=x, y=y,
            vx=math.cos(angle)*speed,
            vy=math.sin(angle)*speed * (1.5 if style=='burst' else 0.8),
            color=color, size=size, life=life, max_life=life,
        ))

def emit_stars(x, y):
    colors = ['#FFD700','#FFF','#FF69B4','#7DF9FF','#ADFF2F']
    for _ in range(25):
        angle = random.uniform(0, 2*math.pi)
        speed = random.uniform(0.05, 0.25)
        state['particles'].append(dict(
            x=x, y=y,
            vx=math.cos(angle)*speed,
            vy=abs(math.sin(angle))*speed + 0.05,
            color=random.choice(colors),
            size=random.uniform(6, 18),
            life=40, max_life=40,
        ))

def emit_explosion(x, y):
    for _ in range(50):
        angle = random.uniform(0, 2*math.pi)
        speed = random.uniform(0.04, 0.3)
        col = random.choice(['#ff1744','#ff6d00','#ffea00','#fff'])
        state['particles'].append(dict(
            x=x, y=y,
            vx=math.cos(angle)*speed,
            vy=math.sin(angle)*speed,
            color=col,
            size=random.uniform(5, 20),
            life=45, max_life=45,
        ))

def emit_freeze(x, y):
    for _ in range(30):
        angle = random.uniform(0, 2*math.pi)
        speed = random.uniform(0.02, 0.12)
        state['particles'].append(dict(
            x=x, y=y,
            vx=math.cos(angle)*speed,
            vy=math.sin(angle)*speed,
            color=random.choice(['#80d8ff','#e1f5fe','#b3e5fc','#ffffff']),
            size=random.uniform(3, 10),
            life=35, max_life=35,
        ))

def emit_crack(x, y):
    for _ in range(20):
        angle = random.uniform(0, 2*math.pi)
        speed = random.uniform(0.02, 0.1)
        state['particles'].append(dict(
            x=x, y=y,
            vx=math.cos(angle)*speed,
            vy=-abs(math.sin(angle))*speed*0.5,
            color=random.choice(['#fffde7','#f9a825','#fff59d']),
            size=random.uniform(3, 9),
            life=25, max_life=25,
        ))

# ─── DRAW FUNCTIONS ────────────────────────────────────────────────

def draw_sky(t):
    """Animated gradient sky"""
    hue = (t * 0.3) % 360
    n = 20
    for i in range(n):
        frac = i / n
        r = 0.04 + 0.06*math.sin(t*0.02 + frac*2)
        g = 0.04 + 0.04*frac
        b = 0.12 + 0.10*frac + 0.05*math.sin(t*0.015)
        rect = plt.Rectangle((-W/2, i*H/n), W, H/n,
                              fc=(r,g,b), ec='none', zorder=0)
        ax.add_patch(rect)

def draw_stars(t):
    """Twinkling stars"""
    rng = np.random.RandomState(42)
    xs = rng.uniform(-W/2, W/2, 60)
    ys = rng.uniform(4.5, H, 60)
    phases = rng.uniform(0, 2*math.pi, 60)
    sizes = rng.uniform(1, 4, 60)
    for i, (x, y) in enumerate(zip(xs, ys)):
        alpha = 0.4 + 0.6 * math.sin(t*0.08 + phases[i])**2
        ax.plot(x, y, 'o', color='white', markersize=sizes[i],
                alpha=alpha, zorder=1)

def draw_ground():
    """3D-perspective ground with grid"""
    # Ground base
    ground = plt.Rectangle((-W/2, 0), W, GROUND_Y,
                            fc='#1a3a1a', ec='#2d5a2d', linewidth=1, zorder=2)
    ax.add_patch(ground)
    # Perspective grid lines
    for xi in np.linspace(-W/2, W/2, 12):
        alpha = 0.25 + 0.1*abs(xi)/(W/2)
        ax.plot([xi, xi*0.3], [GROUND_Y, GROUND_Y*0.2],
                color='#4caf50', alpha=alpha, lw=0.5, zorder=3)
    # Ground highlight
    ax.plot([-W/2, W/2], [GROUND_Y, GROUND_Y], color='#66bb6a', lw=1.5,
            alpha=0.7, zorder=4)

def draw_3d_egg(x, y, etype, angle=0, scale=1.0, alpha=1.0):
    """Draw a stylized pseudo-3D egg"""
    cfg = EGG_TYPES[etype]
    r = EGG_RADIUS * scale

    # Shadow
    shadow = Ellipse((x, GROUND_Y + 0.07), r*2.2, r*0.4,
                     fc='black', ec='none', alpha=min(0.4, alpha*0.5*(1-(y-GROUND_Y)/H)),
                     zorder=4)
    ax.add_patch(shadow)

    # 3D shaded body (stacked ellipses for depth)
    for depth in [3, 2, 1, 0]:
        shade = depth / 4.0
        dx = -0.015 * depth
        dy = -0.008 * depth
        r_scale = 1.0 - depth * 0.03
        col = lerp_color(cfg['color'], '#000022', shade * 0.35)
        egg_body = Ellipse((x + dx + math.sin(angle)*0.04,
                            y + dy + math.cos(angle)*0.04),
                           r * 1.8 * r_scale,
                           r * 2.3 * r_scale,
                           fc=(*col[:3], alpha), ec='none', zorder=5+depth)
        ax.add_patch(egg_body)

    # Highlight (specular)
    highlight = Ellipse((x - r*0.3, y + r*0.4), r*0.5, r*0.3,
                        fc=(1,1,1, min(0.7, alpha*0.9)), ec='none', zorder=10)
    ax.add_patch(highlight)

    # Outline / special markers
    outline = Ellipse((x, y), r*1.85, r*2.35,
                      fc='none', ec=cfg['outline'],
                      linewidth=1.5, alpha=min(1, alpha*1.2), zorder=11)
    ax.add_patch(outline)

    # Special icons
    if etype == 'bomb':
        ax.plot(x, y + r*0.8, 's', color='#ff1744', markersize=4, zorder=12, alpha=alpha)
        ax.plot(x, y + r*1.1, 'o', color='orange', markersize=3, zorder=12, alpha=alpha)
    elif etype == 'golden':
        ax.plot(x, y, '*', color='#FF8C00', markersize=8, zorder=12, alpha=alpha)
    elif etype == 'freeze':
        ax.plot(x, y, '+', color='white', markersize=8, markeredgewidth=2, zorder=12, alpha=alpha)
    elif etype == 'multi':
        ax.plot(x, y, 'D', color='white', markersize=5, zorder=12, alpha=alpha)

def draw_3d_basket(bx, t):
    """Elaborate 3D basket with handles and weave effect"""
    bw = BASKET_W
    bh = 0.55
    by = GROUND_Y

    has_shield = 'shield' in state['active_powerups']
    has_magnet = 'magnet' in state['active_powerups']

    # Shadow
    shadow = Ellipse((bx, by + 0.05), bw*1.3, 0.18,
                     fc='black', ec='none', alpha=0.35, zorder=5)
    ax.add_patch(shadow)

    # Back side of basket (3D depth)
    for depth_i in range(4, 0, -1):
        shade = depth_i / 5.0
        col = lerp_color('#8B4513', '#3d1a05', shade * 0.5)
        rect_d = FancyBboxPatch(
            (bx - bw/2 + depth_i*0.012, by + depth_i*0.012 - bh),
            bw - depth_i*0.024, bh,
            boxstyle="round,pad=0.03",
            fc=col, ec='none', alpha=0.85, zorder=6+depth_i
        )
        ax.add_patch(rect_d)

    # Main basket body
    basket_col = '#c87941' if not has_shield else '#69f0ae'
    basket = FancyBboxPatch(
        (bx - bw/2, by - bh), bw, bh,
        boxstyle="round,pad=0.05",
        fc=basket_col, ec='#6d3200', linewidth=2.0, zorder=11
    )
    ax.add_patch(basket)

    # Weave pattern
    for i, wx in enumerate(np.linspace(bx - bw/2 + 0.1, bx + bw/2 - 0.1, 7)):
        for j, wy in enumerate(np.linspace(by - bh + 0.07, by - 0.07, 4)):
            col_w = '#a0522d' if (i+j)%2==0 else '#cd853f'
            ax.plot(wx, wy, 's', color=col_w, markersize=3.5, zorder=12)

    # Rim of basket (top edge highlight)
    rim = FancyBboxPatch(
        (bx - bw/2, by - 0.10), bw, 0.12,
        boxstyle="round,pad=0.02",
        fc='#deb887', ec='#8B4513', linewidth=1.5, zorder=13
    )
    ax.add_patch(rim)

    # Handles
    for sign in [-1, 1]:
        hx = bx + sign * bw * 0.38
        handle = mpatches.Arc((hx, by - 0.07), 0.25, 0.3,
                               angle=0, theta1=0, theta2=180,
                               color='#6d3200', linewidth=2.5, zorder=14)
        ax.add_patch(handle)

    # Shield aura
    if has_shield:
        remaining = state['active_powerups']['shield'] - state['t']
        pulse = 0.8 + 0.2*math.sin(state['t'] * 0.3)
        shield_circle = Ellipse((bx, by - bh/2), bw*1.5, bh*1.8,
                                 fc='none', ec='#69f0ae',
                                 linewidth=2.5*pulse, alpha=0.6*pulse, zorder=20,
                                 linestyle='--')
        ax.add_patch(shield_circle)

    # Magnet aura
    if has_magnet:
        pulse = 0.7 + 0.3*math.sin(state['t'] * 0.5)
        magnet_aura = Ellipse((bx, by - bh/2), bw*2.2, bh*3.0,
                               fc='none', ec='#ff80ab',
                               linewidth=2.0*pulse, alpha=0.4*pulse, zorder=19,
                               linestyle=':')
        ax.add_patch(magnet_aura)

def draw_duck(cx, cy, i, wobble, t, colors):
    """Draw a stylized 3D-look duck/chicken"""
    c1, c2 = colors
    bob = math.sin(t * 0.07 + i * 1.2) * 0.08
    cy_b = cy + bob + wobble * 0.15

    # Drop shadow
    shadow = Ellipse((cx, DUCK_Y - 0.15), 0.85, 0.18,
                     fc='black', ec='none', alpha=0.3, zorder=4)
    ax.add_patch(shadow)

    # Body (3D layered ellipses)
    for depth in [3, 2, 1, 0]:
        shade = depth / 4.0
        bcol = lerp_color(c1, '#111', shade * 0.4)
        body = Ellipse((cx - depth*0.018, cy_b + depth*0.015),
                       0.72 - depth*0.04, 0.52 - depth*0.03,
                       fc=(*bcol[:3], 0.95), ec='none', zorder=5+depth)
        ax.add_patch(body)

    # Body outline
    body_out = Ellipse((cx, cy_b), 0.72, 0.52,
                       fc='none', ec='black', linewidth=1.2, alpha=0.5, zorder=9)
    ax.add_patch(body_out)

    # Wing (left)
    wing_angle = 15 + 20 * math.sin(t * 0.07 + i)
    wing = Wedge((cx - 0.25, cy_b - 0.05), 0.38, 200, 200 + wing_angle,
                 fc=c2, ec='black', linewidth=0.8, alpha=0.9, zorder=8)
    ax.add_patch(wing)
    # Wing (right mirror)
    wing_r = Wedge((cx + 0.25, cy_b - 0.05), 0.38, -20+wing_angle*0.5, -20,
                   fc=c2, ec='black', linewidth=0.8, alpha=0.9, zorder=8)
    ax.add_patch(wing_r)

    # Highlight on body
    highlight = Ellipse((cx - 0.12, cy_b + 0.1), 0.28, 0.18,
                        fc='white', ec='none', alpha=0.25, zorder=10)
    ax.add_patch(highlight)

    # Head
    head_col = lerp_color(c1, 'white', 0.2)
    head = Circle((cx + 0.22, cy_b + 0.30), 0.22,
                  fc=head_col, ec='black', linewidth=1.0, zorder=10)
    ax.add_patch(head)

    # Eye
    eye = Circle((cx + 0.30, cy_b + 0.36), 0.055,
                 fc='black', ec='none', zorder=11)
    ax.add_patch(eye)
    eye_shine = Circle((cx + 0.32, cy_b + 0.38), 0.022,
                       fc='white', ec='none', zorder=12)
    ax.add_patch(eye_shine)

    # Beak
    beak_pts = np.array([[cx+0.43, cy_b+0.29], [cx+0.52, cy_b+0.25],
                          [cx+0.43, cy_b+0.23]])
    beak = plt.Polygon(beak_pts, fc='#FF8C00', ec='#c8640a',
                       linewidth=0.8, zorder=11)
    ax.add_patch(beak)

    # Comb / crest
    for ci in range(3):
        cx2 = cx + 0.13 + ci * 0.05
        cy2 = cy_b + 0.50 + ci * 0.04
        comb = Circle((cx2, cy2), 0.07 - ci*0.01,
                      fc='#f44336', ec='#b71c1c', linewidth=0.6, zorder=11)
        ax.add_patch(comb)

    # Legs
    for sign, lx in [(-1, cx - 0.12), (1, cx + 0.08)]:
        leg_bob = math.sin(t * 0.07 + i + sign) * 0.05
        ax.plot([lx, lx + sign*0.06], [cy_b - 0.26, cy_b - 0.42 + leg_bob],
                color='#FF8C00', lw=2.5, zorder=9, solid_capstyle='round')
        # Foot
        ax.plot([lx + sign*0.06, lx + sign*0.14], [cy_b - 0.42 + leg_bob, cy_b - 0.44 + leg_bob],
                color='#FF8C00', lw=2.0, zorder=9)

    # Wattle
    wattle = Ellipse((cx + 0.38, cy_b + 0.22), 0.08, 0.12,
                     fc='#ef5350', ec='none', alpha=0.85, zorder=10)
    ax.add_patch(wattle)

def draw_powerup(p, t):
    cfg = POWERUP_TYPES[p['ptype']]
    x, y = p['x'], p['y']
    pulse = 0.85 + 0.15 * math.sin(t * 0.2)
    spin = p['angle']

    # Glow
    glow = Circle((x, y), 0.35*pulse,
                  fc=hex_alpha(cfg['color'], 0.25*pulse),
                  ec=cfg['color'], linewidth=1.5, zorder=14)
    ax.add_patch(glow)

    # Star shape
    star = plt.Polygon(star_points(x, y, 5, 0.22*pulse, 0.12*pulse, spin),
                       fc=cfg['color'], ec='white', linewidth=1.0, zorder=15)
    ax.add_patch(star)

    ax.text(x, y - 0.52, cfg['label'], ha='center', va='center',
            fontsize=7, fontweight='bold', color='white', zorder=16,
            path_effects=[pe.withStroke(linewidth=2, foreground='black')])

def star_points(cx, cy, n, r_outer, r_inner, angle_offset=0):
    pts = []
    for i in range(n * 2):
        angle = math.pi / n * i + angle_offset
        r = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts

def draw_particles():
    for p in state['particles']:
        alpha = p['life'] / p['max_life']
        size = p['size'] * alpha
        ax.plot(p['x'], p['y'], 'o', color=p['color'],
                markersize=max(0.5, size), alpha=min(1.0, alpha*1.2),
                zorder=18, markeredgewidth=0)

def draw_hud(t):
    """Draw all HUD elements"""
    # Score panel
    score_bg = FancyBboxPatch((-W/2 + 0.1, H - 1.4), 3.5, 1.2,
                               boxstyle="round,pad=0.1",
                               fc=hex_alpha('#0a0a2a', 0.85),
                               ec='#7c4dff', linewidth=2, zorder=50)
    ax.add_patch(score_bg)
    ax.text(-W/2 + 1.85, H - 0.6, f'SCORE: {state["score"]:,}',
            ha='center', va='center', fontsize=14, fontweight='bold',
            color='#ffd740', zorder=51,
            path_effects=[pe.withStroke(linewidth=3, foreground='#4a0080')])

    # Level
    ax.text(-W/2 + 1.85, H - 1.05, f'LEVEL {state["level"]}',
            ha='center', va='center', fontsize=9, color='#b388ff', zorder=51)

    # Lives
    lives_bg = FancyBboxPatch((W/2 - 3.8, H - 1.4), 3.5, 1.2,
                               boxstyle="round,pad=0.1",
                               fc=hex_alpha('#0a0a2a', 0.85),
                               ec='#f44336', linewidth=2, zorder=50)
    ax.add_patch(lives_bg)
    hearts = '❤' * state['lives'] + '🖤' * (3 - state['lives'])
    ax.text(W/2 - 2.05, H - 0.85, hearts,
            ha='center', va='center', fontsize=14, zorder=51)

    # Combo
    if state['combo'] >= 2:
        pulse = 1.0 + 0.12*math.sin(t * 0.35)
        combo_col = '#ff6d00' if state['combo'] < 5 else '#ffea00' if state['combo'] < 10 else '#7df9ff'
        ax.text(0, H - 0.65,
                f'🔥 x{state["combo"]} COMBO!',
                ha='center', va='center',
                fontsize=12 * pulse, fontweight='bold',
                color=combo_col, zorder=52,
                path_effects=[pe.withStroke(linewidth=4, foreground='black')])

    # Active power-ups
    px = -W/2 + 0.2
    for name, expiry in list(state['active_powerups'].items()):
        remaining = max(0, expiry - t)
        cfg = POWERUP_TYPES[name]
        pw_bg = FancyBboxPatch((px, H - 2.8), 1.5, 0.55,
                                boxstyle="round,pad=0.05",
                                fc=hex_alpha(cfg['color'], 0.3),
                                ec=cfg['color'], linewidth=1.5, zorder=50)
        ax.add_patch(pw_bg)
        ax.text(px + 0.75, H - 2.52, f'{cfg["label"]} {remaining:.0f}s',
                ha='center', va='center', fontsize=7, color='white', zorder=51)
        px += 1.7

    # Max combo badge
    if state['max_combo'] >= 5:
        ax.text(W/2 - 0.5, H - 2.3, f'Best: x{state["max_combo"]}',
                ha='right', va='center', fontsize=8, color='#80cbc4', zorder=51,
                path_effects=[pe.withStroke(linewidth=2, foreground='black')])

    # Eggs caught
    ax.text(0, H - 1.25, f'Caught: {state["total_eggs_caught"]}',
            ha='center', va='center', fontsize=8, color='#b0bec5', zorder=51)

def draw_floating_messages(t):
    for msg in state['messages']:
        alpha = msg['life'] / msg['max_life']
        rise = (1 - alpha) * 1.2
        ax.text(msg['x'], msg['y'] + rise, msg['text'],
                ha='center', va='center',
                fontsize=msg.get('size', 11) * (0.8 + 0.2*alpha),
                fontweight='bold',
                color=msg['color'],
                alpha=min(1.0, alpha * 2),
                zorder=60,
                path_effects=[pe.withStroke(linewidth=3, foreground='black')])

def draw_game_over():
    overlay = plt.Rectangle((-W/2, 0), W, H,
                             fc=hex_alpha('#0a0010', 0.88), ec='none', zorder=70)
    ax.add_patch(overlay)
    ax.text(0, H*0.65, '💀 GAME OVER 💀', ha='center', va='center',
            fontsize=28, fontweight='bold', color='#ff1744', zorder=71,
            path_effects=[pe.withStroke(linewidth=6, foreground='#4a0000')])
    ax.text(0, H*0.52, f'Final Score: {state["score"]:,}',
            ha='center', va='center', fontsize=18, color='#ffd740', zorder=71)
    ax.text(0, H*0.42, f'Best Combo: x{state["max_combo"]}',
            ha='center', va='center', fontsize=13, color='#b388ff', zorder=71)
    ax.text(0, H*0.33, f'Eggs Caught: {state["total_eggs_caught"]}',
            ha='center', va='center', fontsize=13, color='#80cbc4', zorder=71)
    ax.text(0, H*0.22, 'Press R to Restart',
            ha='center', va='center', fontsize=14, color='white', zorder=71,
            path_effects=[pe.withStroke(linewidth=3, foreground='black')])

def draw_pause():
    overlay = plt.Rectangle((-W/2, 0), W, H,
                             fc=hex_alpha('#001020', 0.75), ec='none', zorder=70)
    ax.add_patch(overlay)
    pulse = 0.9 + 0.1*math.sin(state['t'] * 0.15)
    ax.text(0, H*0.55, '⏸ PAUSED',
            ha='center', va='center',
            fontsize=30*pulse, fontweight='bold',
            color='#80d8ff', zorder=71,
            path_effects=[pe.withStroke(linewidth=5, foreground='#003050')])
    ax.text(0, H*0.4, 'Press SPACE to continue',
            ha='center', va='center', fontsize=13, color='white', zorder=71)

def draw_level_up_flash():
    if state.get('level_flash', 0) > 0:
        alpha = state['level_flash'] / 40
        overlay = plt.Rectangle((-W/2, 0), W, H,
                                 fc=(0.3, 0.0, 0.8, alpha*0.4), ec='none', zorder=55)
        ax.add_patch(overlay)
        ax.text(0, H*0.5, f'⬆ LEVEL {state["level"]}! ⬆',
                ha='center', va='center',
                fontsize=26 * (0.8 + 0.2*alpha), fontweight='bold',
                color='#ffd740', alpha=alpha, zorder=56,
                path_effects=[pe.withStroke(linewidth=5, foreground='#4a3000')])
        state['level_flash'] -= 1

# ─── GAME LOGIC ────────────────────────────────────────────────────

def update_game():
    s = state
    s['t'] += 1

    if s['paused'] or s['game_over']:
        return

    t = s['t']

    # Move basket
    dx = 0
    if s['key_left']:  dx -= BASKET_SPEED
    if s['key_right']: dx += BASKET_SPEED
    if 'slow' in s['active_powerups']:
        dx *= 0.6  # slow powerup affects basket as well? No - it slows eggs
    s['basket_x'] = max(-W/2 + BASKET_W/2 + 0.1,
                         min(W/2 - BASKET_W/2 - 0.1,
                             s['basket_x'] + dx))

    # Duck wobble animation
    for i in range(5):
        s['duck_wobble'][i] += s['duck_dir'][i] * 0.15
        if abs(s['duck_wobble'][i]) > 1.0:
            s['duck_dir'][i] *= -1

    # Egg speed multiplier
    speed_mult = 0.5 if 'slow' in s['active_powerups'] else 1.0

    # Magnet effect
    magnet_active = 'magnet' in s['active_powerups']

    # Update eggs
    remove_eggs = []
    for egg in s['eggs']:
        if egg['state'] == 'falling':
            # Magnet: pull eggs toward basket
            if magnet_active and egg['etype'] != 'bomb':
                pull = (s['basket_x'] - egg['x']) * 0.04
                egg['x'] += pull
            egg['y'] -= egg['speed'] * speed_mult
            egg['angle'] += egg['spin'] * 0.04

            # Hit ground level (basket zone)
            if egg['y'] <= GROUND_Y + 0.45:
                bx = s['basket_x']
                catch_range = BASKET_W/2 + (0.3 if magnet_active else 0)
                if abs(egg['x'] - bx) < catch_range:
                    # CAUGHT!
                    egg['state'] = 'caught'
                    pts = EGG_TYPES[egg['etype']]['pts']
                    mult = 2 if 'doublepts' in s['active_powerups'] else 1

                    if egg['etype'] == 'bomb':
                        if 'shield' in s['active_powerups']:
                            # Shield absorbs it
                            del s['active_powerups']['shield']
                            add_message(egg['x'], GROUND_Y + 1.0, '🛡 BLOCKED!', '#69f0ae', 14)
                            emit_particles(egg['x'], GROUND_Y + 0.5, '#69f0ae', 25, 'burst')
                        else:
                            s['lives'] -= 1
                            s['combo'] = 0
                            emit_explosion(egg['x'], egg['y'])
                            add_message(egg['x'], GROUND_Y + 1.0, '💥 BOMB!', '#ff1744', 16)
                            s['streak_flash'] = 10
                            if s['lives'] <= 0:
                                s['game_over'] = True
                    elif egg['etype'] == 'freeze':
                        s['freeze_timer'] = FPS * 5
                        emit_freeze(egg['x'], egg['y'])
                        add_message(egg['x'], GROUND_Y + 1.0, '❄ FREEZE!', '#80d8ff', 12)
                        s['score'] += pts * mult
                        s['combo'] += 1
                        s['total_eggs_caught'] += 1
                        emit_stars(egg['x'], egg['y'])
                    elif egg['etype'] == 'multi':
                        # Spawn 3 extra golden eggs
                        for _ in range(3):
                            nx = s['basket_x'] + random.uniform(-1.5, 1.5)
                            s['eggs'].append(dict(
                                x=nx, y=DUCK_Y-0.5, etype='golden',
                                speed=0.08, lane=0, spin=random.uniform(-2,2),
                                angle=0.0, shadow_alpha=0.0, state='falling', explode_t=0))
                        s['score'] += pts * mult
                        s['combo'] += 1
                        s['total_eggs_caught'] += 1
                        add_message(egg['x'], GROUND_Y + 1.0, '🔮 MULTI!', '#e040fb', 14)
                        emit_stars(egg['x'], egg['y'])
                    else:
                        # Normal or golden
                        total_pts = pts * mult * max(1, s['combo'] // 3 + 1)
                        s['score'] += total_pts
                        s['combo'] += 1
                        s['total_eggs_caught'] += 1
                        if s['combo'] > s['max_combo']:
                            s['max_combo'] = s['combo']
                        combo_bonus = ''
                        if s['combo'] >= 10:
                            combo_bonus = '🌟 ULTRA!'
                        elif s['combo'] >= 5:
                            combo_bonus = '🔥 HOT!'
                        if egg['etype'] == 'golden':
                            add_message(egg['x'], GROUND_Y + 1.0, f'+{total_pts} ✨ GOLDEN!', '#FFD700', 13)
                            emit_stars(egg['x'], egg['y'])
                        else:
                            col = '#adff2f' if s['combo'] < 5 else '#ffd740' if s['combo'] < 10 else '#ff6d00'
                            msg = f'+{total_pts}'
                            if combo_bonus: msg += f' {combo_bonus}'
                            add_message(egg['x'], GROUND_Y + 0.9, msg, col, 11)
                            emit_particles(egg['x'], egg['y'], '#fff9c4', 12)

                    remove_eggs.append(egg)

                elif egg['y'] <= GROUND_Y + 0.05:
                    # MISSED
                    egg['state'] = 'missed'
                    if egg['etype'] != 'bomb':
                        s['combo'] = 0
                        emit_crack(egg['x'], egg['y'])
                        add_message(egg['x'], GROUND_Y + 0.6, 'MISSED!', '#ff5722', 10)
                        s['lives'] -= 1
                        if s['lives'] <= 0:
                            s['game_over'] = True
                    remove_eggs.append(egg)

        elif egg['state'] in ('caught', 'missed'):
            remove_eggs.append(egg)

    for e in remove_eggs:
        if e in s['eggs']:
            s['eggs'].remove(e)

    # Spawn eggs
    s['egg_timer'] += 1
    interval = max(30, s['egg_interval'] - s['level'] * 3)
    if s['egg_timer'] >= interval:
        s['egg_timer'] = 0
        spawn_egg()
        # Chance for bonus egg
        if random.random() < 0.25 + s['level'] * 0.04:
            spawn_egg()

    # Spawn powerups
    if random.random() < 0.003 + s['level'] * 0.001:
        spawn_powerup()

    # Update powerups (falling)
    remove_pus = []
    for p in s['powerups']:
        p['y'] -= 0.03
        p['angle'] += 0.08
        if p['y'] < GROUND_Y + 0.35:
            bx = s['basket_x']
            if abs(p['x'] - bx) < BASKET_W/2 + 0.2:
                # Collected!
                cfg = POWERUP_TYPES[p['ptype']]
                s['active_powerups'][p['ptype']] = t + FPS * cfg['duration']
                add_message(p['x'], GROUND_Y + 1.2, f'{cfg["label"]} ACTIVATED!', cfg['color'], 12)
                emit_particles(p['x'], p['y'], cfg['color'], 20, 'burst')
            remove_pus.append(p)
        elif p['y'] < -0.5:
            remove_pus.append(p)
    for p in remove_pus:
        if p in s['powerups']:
            s['powerups'].remove(p)

    # Expire active powerups
    for name in list(s['active_powerups'].keys()):
        if s['active_powerups'][name] <= t:
            del s['active_powerups'][name]
            add_message(0, H/2, f'{POWERUP_TYPES[name]["label"]} expired', '#546e7a', 9)

    # Update particles
    remove_p = []
    for p in s['particles']:
        p['x'] += p['vx']
        p['y'] += p['vy']
        p['vy'] -= 0.005  # gravity
        p['life'] -= 1
        if p['life'] <= 0:
            remove_p.append(p)
    for p in remove_p:
        s['particles'].remove(p)

    # Update floating messages
    remove_m = []
    for m in s['messages']:
        m['life'] -= 1
        if m['life'] <= 0:
            remove_m.append(m)
    for m in remove_m:
        s['messages'].remove(m)

    # Level progression
    thresholds = [0, 30, 80, 150, 250, 400, 600, 900, 1300, 1800, 2500]
    new_level = 1
    for i, thresh in enumerate(thresholds):
        if s['score'] >= thresh:
            new_level = i + 1
    if new_level > s['level']:
        s['level'] = new_level
        s['level_flash'] = 55
        add_message(0, H*0.55, f'🆙 LEVEL UP! → {new_level}', '#ffd740', 18)
        emit_stars(0, H*0.5)

def add_message(x, y, text, color, size=11):
    state['messages'].append(dict(
        x=x, y=y, text=text, color=color, size=size,
        life=55, max_life=55
    ))

# ─── MAIN ANIMATION LOOP ───────────────────────────────────────────

def animate(frame):
    ax.cla()
    ax.set_facecolor('#0a0a1a')
    ax.set_xlim(-W/2, W/2)
    ax.set_ylim(0, H)
    ax.set_aspect('equal')
    ax.axis('off')

    t = state['t']

    # Background
    draw_sky(t)
    draw_stars(t)
    draw_ground()

    if not state['game_over'] and not state['paused']:
        update_game()

    # Draw ducks
    for i, dx in enumerate(LANE_XS):
        draw_duck(dx, DUCK_Y, i, state['duck_wobble'][i], t, state['duck_colors'][i])

    # Draw powerups
    for p in state['powerups']:
        draw_powerup(p, t)

    # Draw eggs
    for egg in state['eggs']:
        if egg['state'] == 'falling':
            draw_3d_egg(egg['x'], egg['y'], egg['etype'],
                        angle=egg['angle'], scale=1.0)

    # Basket
    draw_3d_basket(state['basket_x'], t)

    # Particles (on top)
    draw_particles()

    # HUD
    draw_hud(t)
    draw_floating_messages(t)
    draw_level_up_flash()

    if state['game_over']:
        draw_game_over()
    elif state['paused']:
        draw_pause()

    # Instruction strip at bottom
    if t < 180 and not state['game_over']:
        ax.text(0, 0.25, '← → to move basket  |  SPACE = pause  |  R = restart',
                ha='center', va='center', fontsize=8, color='#546e7a',
                zorder=50, alpha=max(0, (180-t)/180))

    return []

# ─── INPUT HANDLERS ────────────────────────────────────────────────

def on_key_press(event):
    k = event.key
    if k == 'left':
        state['key_left'] = True
    elif k == 'right':
        state['key_right'] = True
    elif k == ' ':
        if not state['game_over']:
            state['paused'] = not state['paused']
    elif k == 'r':
        reset_game()

def on_key_release(event):
    k = event.key
    if k == 'left':
        state['key_left'] = False
    elif k == 'right':
        state['key_right'] = False

fig.canvas.mpl_connect('key_press_event', on_key_press)
fig.canvas.mpl_connect('key_release_event', on_key_release)

# ─── LAUNCH ────────────────────────────────────────────────────────

print("""
╔══════════════════════════════════════════════════════════════╗
║       🐣  CHICKEN EGG CATCHER 3D  —  ULTRA EDITION  🐣      ║
╠══════════════════════════════════════════════════════════════╣
║  ← →   Move basket                                          ║
║  SPACE  Pause / unpause                                     ║
║  R      Restart                                             ║
╠══════════════════════════════════════════════════════════════╣
║  Egg Types:                                                 ║
║   🥚 Normal  (+1pt)   ✨ Golden (+5pts)                     ║
║   💣 Bomb   (-3pts)   ❄  Freeze (slows eggs 5s)            ║
║   🔮 Multi  (spawns 3 golden eggs!)                         ║
║  Power-Ups (falling stars):                                 ║
║   🛡 Shield  🧲 Magnet  ⏱ Slow  2× Points                  ║
╚══════════════════════════════════════════════════════════════╝
""")

ani = animation.FuncAnimation(fig, animate, interval=1000//FPS,
                               blit=False, cache_frame_data=False)
plt.tight_layout(pad=0)
plt.show()
