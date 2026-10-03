"""Shared tokenisation choices.

The stock English stop word list in scikit learn removes words that carry real
meaning in this domain ("fire", "system", "front", "back", "part", "side"). Dropping
"fire" from a brake safety index is not acceptable, so the project keeps its own
short list of pure function words.
"""

STOP_WORDS = sorted(
    set(
        """a an the and or but if while of at by for with about against between into through during
        before after above below to from up down in out on off over under again further then once here
        there when where why how all any both each few more most other some such nor only own same so
        than too very can will just should now is are was were be been being have has had having do does
        did doing i me my myself we our ours you your yours he him his she her hers it its they them their
        what which who whom this that these those am would could also as""".split()
    )
)
