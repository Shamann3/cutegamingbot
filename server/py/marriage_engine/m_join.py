# -*- coding: utf-8 -*-
from marriage_engine.m_ids import *
from marriage_engine.m_lv1 import A as _LA
from marriage_engine.m_lv2 import B as _LB
LEVELS = _LA + _LB
from marriage_engine.m_gf1 import G1
from marriage_engine.m_gf2 import G2
from marriage_engine.m_gf3 import G3
from marriage_engine.m_gf4 import G4
from marriage_engine.m_gf5 import G5
from marriage_engine.m_gf6 import G6
from marriage_engine.m_rt1 import R1
from marriage_engine.m_rt2 import R2
GIFTS, RITES = G1 + G2 + G3 + G4 + G5 + G6, R1 + R2
from marriage_engine.m_pack import *
