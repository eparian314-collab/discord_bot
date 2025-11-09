import matplotlib.pyplot as plt
import io

def generate_confidence_graph(history: list[float], stability: float) -> bytes:
    plt.figure(figsize=(6, 3))
    plt.plot(history, label='OCR Confidence', color='blue', linewidth=2)
    if history:
        avg_conf = sum(history) / len(history)
        plt.axhline(avg_conf, color='green', linestyle='--', label=f'Avg: {avg_conf:.2f}')
        plt.axhline(0.65, color='red', linestyle=':', label='Threshold: 0.65')
    plt.ylim(0, 1)
    plt.xlabel('Submission #')
    plt.ylabel('Confidence')
    plt.title('OCR Confidence Trend')
    plt.legend(loc='lower right')
    plt.text(0.02, 0.92, f'Stability: {stability:.2f}', transform=plt.gca().transAxes, fontsize=10, color='purple', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    return buf.getvalue()
