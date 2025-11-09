import matplotlib.pyplot as plt
import numpy as np
import io
from statistics import mean, stdev

def generate_momentum_map(guild_id, history) -> bytes:
    names = []
    momenta = []
    stabilities = []
    colors = []
    for name, scores in history.items():
        if not scores:
            continue
        last = scores[-1]
        avg = mean(scores)
        momentum = (last - avg) / max(avg, 1)
        stability = 1 / (stdev(scores) + 0.001) if len(scores) > 1 else 1.0
        if momentum > 0.08:
            color = 'green'
        elif momentum < -0.08:
            color = 'orange'
        else:
            color = 'blue'
        names.append(name)
        momenta.append(momentum)
        stabilities.append(stability)
        colors.append(color)
    plt.figure(figsize=(7, 5))
    scatter = plt.scatter(momenta, stabilities, c=colors, s=80, alpha=0.8, edgecolors='k')
    # Annotate top 8 by stability
    if names:
        top_idx = np.argsort(stabilities)[-8:]
        for idx in top_idx:
            plt.annotate(names[idx], (momenta[idx], stabilities[idx]), fontsize=9, ha='right', va='bottom')
    plt.xlabel('Momentum (Change from Avg)')
    plt.ylabel('Stability (Inverse Variance)')
    plt.title(f'Guild Momentum Map - {guild_id}')
    plt.grid(True, linestyle='--', alpha=0.5)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    return buf.getvalue()
