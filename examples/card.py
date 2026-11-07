"""An example card on a synthetic item: the prompt verbatim with its key word in bold, each method's answer before and
after each change, and a small note with how the item was picked and its id. Direct labels: every colour is words."""

from __future__ import annotations

import styles_plot as sp


def card(v: sp.Vocab) -> sp.Figure:
    c = sp.Card(
        prompt=[("The violin is in the third locker. The ", None), ("flute", None, True),
                (" is in the first one. Which locker holds the violin?", None)],
        columns=["before", "the whole change", "without the probe", "without a random direction"],
        rows=[sp.CardRow("alpha", "first", {"before": "the third locker", "the whole change": "the first locker",
                                              "without the probe": "the third locker",
                                              "without a random direction": "the first locker"}),
              sp.CardRow("beta", "second", {"before": "the third locker", "the whole change": "the third locker",
                                             "without the probe": "the third locker",
                                             "without a random direction": "the third locker"})],
        note="synthetic data · picked as the first item that both methods answer right before the change · item_0007",
    )  # fmt: skip
    return sp.Figure("card", v, direct_labels=True).add(c)


FIGURES = (card,)
