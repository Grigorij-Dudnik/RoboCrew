"""MolmoAct2 remote-inference support for the SO-101 arm.

Minimal extract of the molmo_so101 client/runtime needed to drive MolmoAct2 as a
RoboCrew tool. The GPU-heavy model runs out-of-process via serve.py; the robot
box talks to it with RemotePolicyClient (TCP + pickle) and never imports torch.
"""
