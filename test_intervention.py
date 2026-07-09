import sys
import os
import sitecustomize

def test():
    raise sitecustomize.NeedsAgentInterventionError("Testing intervention error")

if __name__ == "__main__":
    test()
