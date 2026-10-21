"""Headless training diagnostics, updated after every epoch."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def plot_history(history, output):
    epochs = [r['epoch'] for r in history]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), constrained_layout=True)
    panels = [
        ('Total loss', [('train_loss', 'Train'), ('loss', 'Validation')]),
        ('Classification focal loss', [('train_cls_loss', 'Train'), ('cls_loss', 'Validation')]),
        ('Box Smooth L1 loss (before x5)', [('train_box_loss', 'Train'), ('box_loss', 'Validation')]),
        ('Learning rate (used this epoch)', [('lr', 'LR')]),
        ('Validation at IoU 0.5', [('precision', 'Precision'), ('recall', 'Recall')]),
        ('Gradient norm before clipping', [('grad_norm', 'Mean batch norm')]),
    ]
    for ax, (title, series) in zip(axes.flat, panels):
        for key, label in series:
            ax.plot(epochs, [r[key] for r in history], label=label, marker='.' if len(epochs)<3 else None)
        ax.set(title=title, xlabel='Epoch')
        ax.grid(alpha=.25)
        ax.legend()
    axes[1,1].set_ylim(0,1.05)
    axes[1,2].axhline(10,color='gray',linestyle='--',label='Clip threshold: 10')
    axes[1,2].legend()
    fig.suptitle('TinyFace training — validation uses teacher pseudo-labels')
    fig.savefig(output,dpi=150)
    plt.close(fig)
