# NLP written by GAMS Convert at 02/17/22 17:18:03
#
# Equation counts
#     Total        E        G        L        N        X        C        B
#        95       95        0        0        0        0        0        0
#
# Variable counts
#                  x        b        i      s1s      s2s       sc       si
#     Total     cont   binary  integer     sos1     sos2    scont     sint
#        96       96        0        0        0        0        0        0
# FX      0
#
# Nonzero counts
#     Total    const       NL
#       407      367       40
#
# Reformulation has removed 1 variable and 1 equation

from pyomo.environ import *

model = m = ConcreteModel()

m.x1 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x2 = Var(within=Reals, bounds=(61.511,100), initialize=61.511)
m.x3 = Var(within=Reals, bounds=(25.3199,44.4401), initialize=25.3199)
m.x4 = Var(within=Reals, bounds=(0,1), initialize=0)
m.x5 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x6 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x7 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x8 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x9 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x10 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x11 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x12 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x13 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x14 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x15 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x16 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x17 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x18 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x19 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x20 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x21 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x22 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x23 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x24 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x25 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x26 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x27 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x28 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x29 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x30 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x31 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x32 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x33 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x34 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x35 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x36 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x37 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x38 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x39 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x40 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x41 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x42 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x43 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x44 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x45 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x46 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x47 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x48 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x49 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x50 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x51 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x52 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x53 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x54 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x55 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x56 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x57 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x58 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x59 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x60 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x61 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x62 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x63 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x64 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x65 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x66 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x67 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x68 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x69 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x70 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x71 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x72 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x73 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x74 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x75 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x76 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x77 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x78 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x79 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x80 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x81 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x82 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x83 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x84 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x85 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x86 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x87 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x88 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x89 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x90 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x91 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x92 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x93 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x94 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x95 = Var(within=Reals, bounds=(None,None), initialize=0)
m.x96 = Var(within=Reals, bounds=(None,None), initialize=0)

m.obj = Objective(sense=minimize, expr= 120.40939193257074 * m.x29 * m.x4 +
    120.40939193257074 * m.x75 * (1 - m.x4))

m.e1 = Constraint(expr= m.x1 == 4.5)
m.e2 = Constraint(expr= m.x2 - 100 * m.x4 == 0)
m.e3 = Constraint(expr= m.x3 + 100 * m.x4 == 100)
m.e4 = Constraint(expr= -m.x2 + m.x5 == 0)
m.e5 = Constraint(expr= -m.x1 + m.x6 == 0)
m.e6 = Constraint(expr= -0.04 * m.x5 + m.x7 == -3)
m.e7 = Constraint(expr= -0.3448275862068966 * m.x6 + m.x8
    == -1.4137931034482758)
m.e8 = Constraint(expr= -3.29883729878545 * m.x7 - 2.21634281184627 * m.x8 +
    m.x31 == -4.74519636814514)
m.e9 = Constraint(expr= -4.39097392620389 * m.x7 + 2.70229300136141 * m.x8 +
    m.x32 == -4.1794539909462)
m.e10 = Constraint(expr= 2.42525489414387 * m.x7 - 2.14396438801434 * m.x8 +
    m.x33 == 1.78401467718833)
m.e11 = Constraint(expr= -0.665434334521876 * m.x7 + 1.29787993619185 * m.x8 +
    m.x34 == -1.11674460513219)
m.e12 = Constraint(expr= 2.77766394913542 * m.x7 + 1.74555017902411 * m.x8 +
    m.x35 == 0.597624173984931)
m.e13 = Constraint(expr= -4.7733972839648 * m.x7 + 2.41673394043034 * m.x8 +
    m.x36 == 1.42752748364808)
m.e14 = Constraint(expr= -2.4663429726711 * m.x7 + 2.38573916130801 * m.x8 +
    m.x37 == 1.17440914003301)
m.e15 = Constraint(expr= 5.52466754531544 * m.x7 - 2.06923017046543 * m.x8 +
    m.x38 == -2.90717074600284)
m.e16 = Constraint(expr= -3.61637061682719 * m.x7 + 5.51456412860865 * m.x8 +
    m.x39 == 5.64272390748818)
m.e17 = Constraint(expr= 0.995512979228518 * m.x7 - 4.09187475401507 * m.x8 +
    m.x40 == -3.89340599335458)
m.e18 = Constraint(expr= 2 / (exp(2 * m.x31) + 1) + m.x9 == 1)
m.e19 = Constraint(expr= 2 / (exp(2 * m.x32) + 1) + m.x10 == 1)
m.e20 = Constraint(expr= 2 / (exp(2 * m.x33) + 1) + m.x11 == 1)
m.e21 = Constraint(expr= 2 / (exp(2 * m.x34) + 1) + m.x12 == 1)
m.e22 = Constraint(expr= 2 / (exp(2 * m.x35) + 1) + m.x13 == 1)
m.e23 = Constraint(expr= 2 / (exp(2 * m.x36) + 1) + m.x14 == 1)
m.e24 = Constraint(expr= 2 / (exp(2 * m.x37) + 1) + m.x15 == 1)
m.e25 = Constraint(expr= 2 / (exp(2 * m.x38) + 1) + m.x16 == 1)
m.e26 = Constraint(expr= 2 / (exp(2 * m.x39) + 1) + m.x17 == 1)
m.e27 = Constraint(expr= 2 / (exp(2 * m.x40) + 1) + m.x18 == 1)
m.e28 = Constraint(expr= 0.398852142813582 * m.x9 - 0.725357344120736 * m.x10
    - 0.387983353041334 * m.x11 - 0.391659415559979 * m.x12 +
    0.288302309312186 * m.x13 - 0.849799453052077 * m.x14 - 0.217992356329322 *
    m.x15 + 0.486032972888755 * m.x16 + 0.633874608504516 * m.x17 +
    0.650057770234234 * m.x18 + m.x41 == 1.72952444050299)
m.e29 = Constraint(expr= -0.606108375762298 * m.x9 + 1.05128271107625 * m.x10
    - 0.113407401402558 * m.x11 - 0.685128435722532 * m.x12 -
    0.00839355729502805 * m.x13 + 0.72324079108208 * m.x14 - 1.54800905346302 *
    m.x15 + 0.739614279155593 * m.x16 - 0.0672266652749378 * m.x17 -
    0.862069039273904 * m.x18 + m.x42 == -1.82152313507679)
m.e30 = Constraint(expr= 0.017213005528439 * m.x9 - 0.432991382826051 * m.x10
    - 0.526615385996248 * m.x11 - 1.74111228306707 * m.x12 +
    0.0927253728709128 * m.x13 - 0.714238249447 * m.x14 - 2.30412079128021 *
    m.x15 - 0.307687532319036 * m.x16 + 0.685277679084365 * m.x17 +
    0.298152813152174 * m.x18 + m.x43 == -1.94871746897132)
m.e31 = Constraint(expr= -0.254425130089128 * m.x9 + 0.982857591863807 * m.x10
    - 1.12188627220446 * m.x11 + 0.953177569130776 * m.x12 + 1.16324832732783
    * m.x13 - 0.583334671787914 * m.x14 - 1.46286282166184 * m.x15 -
    0.740744196362748 * m.x16 + 0.156187890973621 * m.x17 + 0.473721758540603 *
    m.x18 + m.x44 == 0.750110448454269)
m.e32 = Constraint(expr= 0.358841679803966 * m.x9 - 0.909769646581453 * m.x10
    - 0.5400556368999 * m.x11 - 1.92581231012236 * m.x12 - 0.143289578857379 *
    m.x13 + 1.11041979527607 * m.x14 - 0.806556686522453 * m.x15 +
    1.31979752840351 * m.x16 - 2.83201899803365 * m.x17 - 1.4165064435108 *
    m.x18 + m.x45 == -0.155525493921263)
m.e33 = Constraint(expr= 0.876963350723843 * m.x9 + 1.68895367151327 * m.x10 -
    1.01792289921342 * m.x11 + 0.481816149447196 * m.x12 - 0.681037723637203 *
    m.x13 - 0.221547242667722 * m.x14 - 0.153701721119032 * m.x15 -
    0.387789381638438 * m.x16 - 0.534863109743709 * m.x17 + 0.429118392881899 *
    m.x18 + m.x46 == -0.182171157802204)
m.e34 = Constraint(expr= 0.295071408357937 * m.x9 + 0.615013493949934 * m.x10
    - 0.477319899374172 * m.x11 + 0.669337407546281 * m.x12 -
    0.659568388812123 * m.x13 - 2.87966615253197 * m.x14 - 1.18319325324759 *
    m.x15 - 0.317508919826113 * m.x16 - 0.0260541413647632 * m.x17 -
    0.613914515498283 * m.x18 + m.x47 == -0.525879231367697)
m.e35 = Constraint(expr= -0.276877372242598 * m.x9 - 0.313761370734112 * m.x10
    + 0.437283574367938 * m.x11 + 1.40935113091552 * m.x12 - 0.239224962403201
    * m.x13 + 1.25079738013603 * m.x14 - 0.862457167086818 * m.x15 +
    0.728247439675487 * m.x16 - 0.422374486028782 * m.x17 - 1.57017436743666 *
    m.x18 + m.x48 == 0.851092831485534)
m.e36 = Constraint(expr= 0.0222234768795211 * m.x9 - 0.17355526816404 * m.x10
    + 1.15591927972987 * m.x11 + 1.98476876674976 * m.x12 + 0.10670750595954 *
    m.x13 + 0.363095670968738 * m.x14 + 1.67891067831231 * m.x15 +
    0.581167798267274 * m.x16 - 0.201190601410721 * m.x17 + 0.862612980547481 *
    m.x18 + m.x49 == 1.74557292553105)
m.e37 = Constraint(expr= 1.5513910853905 * m.x9 - 1.468539025819 * m.x10 -
    0.106950283907874 * m.x11 - 2.47794942642174 * m.x12 - 0.120836180137454 *
    m.x13 - 0.189856190121489 * m.x14 - 0.488776919915584 * m.x15 -
    0.299287142871813 * m.x16 - 0.786524342476143 * m.x17 - 0.171942752553922 *
    m.x18 + m.x50 == -1.52550869349925)
m.e38 = Constraint(expr= 2 / (exp(2 * m.x41) + 1) + m.x19 == 1)
m.e39 = Constraint(expr= 2 / (exp(2 * m.x42) + 1) + m.x20 == 1)
m.e40 = Constraint(expr= 2 / (exp(2 * m.x43) + 1) + m.x21 == 1)
m.e41 = Constraint(expr= 2 / (exp(2 * m.x44) + 1) + m.x22 == 1)
m.e42 = Constraint(expr= 2 / (exp(2 * m.x45) + 1) + m.x23 == 1)
m.e43 = Constraint(expr= 2 / (exp(2 * m.x46) + 1) + m.x24 == 1)
m.e44 = Constraint(expr= 2 / (exp(2 * m.x47) + 1) + m.x25 == 1)
m.e45 = Constraint(expr= 2 / (exp(2 * m.x48) + 1) + m.x26 == 1)
m.e46 = Constraint(expr= 2 / (exp(2 * m.x49) + 1) + m.x27 == 1)
m.e47 = Constraint(expr= 2 / (exp(2 * m.x50) + 1) + m.x28 == 1)
m.e48 = Constraint(expr= -1.0674 * m.x19 + 1.2197 * m.x20 - 1.578 * m.x21 +
    1.4501 * m.x22 + 1.0611 * m.x23 + 0.52263 * m.x24 + 0.090589 * m.x25 -
    0.78946 * m.x26 - 1.7347 * m.x27 + 0.63854 * m.x28 + m.x30
    == -0.523544433780434)
m.e49 = Constraint(expr= m.x29 - 136.23687745314615 * m.x30
    == 165.14897153681486)
m.e50 = Constraint(expr= -m.x3 + m.x51 == 0)
m.e51 = Constraint(expr= -m.x1 + m.x52 == 0)
m.e52 = Constraint(expr= -0.05714285714285714 * m.x51 + m.x53
    == -1.8571428571428572)
m.e53 = Constraint(expr= -0.3448275862068966 * m.x52 + m.x54
    == -1.4137931034482758)
m.e54 = Constraint(expr= 4.93640448594107 * m.x53 + 0.912605578908679 * m.x54
    + m.x77 == 4.1270692338668)
m.e55 = Constraint(expr= 0.816777467188004 * m.x53 + 5.32033684666278 * m.x54
    + m.x78 == -2.32662461492317)
m.e56 = Constraint(expr= 2.66472390799182 * m.x53 + 0.362343664737007 * m.x54
    + m.x79 == 1.91392918798187)
m.e57 = Constraint(expr= 2.02628709921665 * m.x53 + 0.48093844474148 * m.x54 +
    m.x80 == 0.427660620779721)
m.e58 = Constraint(expr= -1.14069543363375 * m.x53 + 3.45428737671842 * m.x54
    + m.x81 == -1.71791138693198)
m.e59 = Constraint(expr= -1.73507877664684 * m.x53 - 3.91745010409221 * m.x54
    + m.x82 == 1.09025760296775)
m.e60 = Constraint(expr= -2.11707508608896 * m.x53 + 2.33023244949126 * m.x54
    + m.x83 == 1.50363786298596)
m.e61 = Constraint(expr= -2.99151042883558 * m.x53 + 3.93409732391626 * m.x54
    + m.x84 == -0.0181541866671218)
m.e62 = Constraint(expr= -1.5250601954822 * m.x53 - 3.17883210470949 * m.x54 +
    m.x85 == 3.45453898493558)
m.e63 = Constraint(expr= -1.46971647430401 * m.x53 + 3.34372673401725 * m.x54
    + m.x86 == 5.31141965926459)
m.e64 = Constraint(expr= 2 / (exp(2 * m.x77) + 1) + m.x55 == 1)
m.e65 = Constraint(expr= 2 / (exp(2 * m.x78) + 1) + m.x56 == 1)
m.e66 = Constraint(expr= 2 / (exp(2 * m.x79) + 1) + m.x57 == 1)
m.e67 = Constraint(expr= 2 / (exp(2 * m.x80) + 1) + m.x58 == 1)
m.e68 = Constraint(expr= 2 / (exp(2 * m.x81) + 1) + m.x59 == 1)
m.e69 = Constraint(expr= 2 / (exp(2 * m.x82) + 1) + m.x60 == 1)
m.e70 = Constraint(expr= 2 / (exp(2 * m.x83) + 1) + m.x61 == 1)
m.e71 = Constraint(expr= 2 / (exp(2 * m.x84) + 1) + m.x62 == 1)
m.e72 = Constraint(expr= 2 / (exp(2 * m.x85) + 1) + m.x63 == 1)
m.e73 = Constraint(expr= 2 / (exp(2 * m.x86) + 1) + m.x64 == 1)
m.e74 = Constraint(expr= -0.19229719566531 * m.x55 - 0.113229364819046 * m.x56
    - 0.317011984009582 * m.x57 - 0.208176499331018 * m.x58 -
    0.0526893135225106 * m.x59 + 0.00496874764197475 * m.x60 - 1.11781664691223
    * m.x61 - 0.164747202380028 * m.x62 + 0.128801038943437 * m.x63 -
    0.115050980825826 * m.x64 + m.x87 == -1.61331605529523)
m.e75 = Constraint(expr= -1.39561108328297 * m.x55 + 0.291294577508309 * m.x56
    + 2.42255053970948 * m.x57 + 0.806424775519701 * m.x58 - 0.24700602376048
    * m.x59 - 2.86528129248516 * m.x60 + 0.228041341097786 * m.x61 -
    0.919031862096554 * m.x62 - 0.331591530574725 * m.x63 - 0.862221243067094 *
    m.x64 + m.x88 == -1.14616698593978)
m.e76 = Constraint(expr= -1.5279242841873 * m.x55 - 0.698226236065608 * m.x56
    + 1.55481625080507 * m.x57 - 0.712477732925898 * m.x58 - 0.879321205828354
    * m.x59 - 0.999578930453093 * m.x60 + 0.436064389773445 * m.x61 -
    1.20491503278419 * m.x62 + 0.0828027271237818 * m.x63 + 1.16436684334948 *
    m.x64 + m.x89 == -1.26487905494015)
m.e77 = Constraint(expr= -1.31136556313664 * m.x55 + 0.688090162957568 * m.x56
    - 0.483533126996118 * m.x57 + 0.317208594550559 * m.x58 -
    0.987077283548825 * m.x59 + 2.03966860668343 * m.x60 - 1.28045374550174 *
    m.x61 - 1.17174317918226 * m.x62 - 1.92490816822108 * m.x63 +
    1.88902014251631 * m.x64 + m.x90 == -2.43368306899489)
m.e78 = Constraint(expr= 0.663187111420449 * m.x55 + 0.653673216749544 * m.x56
    - 2.05130150144194 * m.x57 - 0.038085494374431 * m.x58 - 1.47243466819752
    * m.x59 - 2.97625982340582 * m.x60 + 2.99369146603845 * m.x61 -
    1.41254919999138 * m.x62 + 0.792703266075634 * m.x63 - 1.20920862561178 *
    m.x64 + m.x91 == -0.145245935667929)
m.e79 = Constraint(expr= 3.16558479304872 * m.x55 + 0.610800921707547 * m.x56
    - 3.91566418422506 * m.x57 + 0.690696672854988 * m.x58 - 1.1387592986803 *
    m.x59 - 1.55320919936001 * m.x60 - 0.649315965120837 * m.x61 -
    3.93545445106757 * m.x62 - 1.72059703275849 * m.x63 + 0.352306217462982 *
    m.x64 + m.x92 == -0.544825168753145)
m.e80 = Constraint(expr= -0.832946328830514 * m.x55 - 0.261706335203891 * m.x56
    - 1.52961004768381 * m.x57 - 0.96278230549486 * m.x58 - 0.0558260797192328
    * m.x59 + 0.796583270628257 * m.x60 + 0.231506642471326 * m.x61 +
    0.699291918288105 * m.x62 + 0.38426656703623 * m.x63 + 1.46531125311878 *
    m.x64 + m.x93 == 0.336652248890323)
m.e81 = Constraint(expr= 1.95060055587423 * m.x55 + 1.84279061221506 * m.x56 -
    0.225343280513967 * m.x57 + 1.32570761854527 * m.x58 - 0.0145976190506455 *
    m.x59 + 2.3127770319283 * m.x60 - 1.72621008535973 * m.x61 +
    0.913597417647886 * m.x62 + 1.22514837154043 * m.x63 + 0.0387545896912135 *
    m.x64 + m.x94 == -0.182365009499401)
m.e82 = Constraint(expr= 0.45472386490334 * m.x55 - 1.91223566080678 * m.x56 -
    0.537347924651761 * m.x57 + 0.98607719903189 * m.x58 + 0.225915202471944 *
    m.x59 + 2.41658375893019 * m.x60 + 1.5400112823527 * m.x61 -
    0.590930400398464 * m.x62 - 2.14543603917029 * m.x63 - 1.15870755844912 *
    m.x64 + m.x95 == 3.71721040155117)
m.e83 = Constraint(expr= -2.23225023028356 * m.x55 + 0.327733125529555 * m.x56
    + 0.310848878283525 * m.x57 + 1.05010074838177 * m.x58 - 0.831450614261062
    * m.x59 - 0.501691134298998 * m.x60 - 3.24606656818691 * m.x61 +
    0.313457236205627 * m.x62 - 0.58950348835461 * m.x63 + 1.96788365310352 *
    m.x64 + m.x96 == 0.451617778637158)
m.e84 = Constraint(expr= 2 / (exp(2 * m.x87) + 1) + m.x65 == 1)
m.e85 = Constraint(expr= 2 / (exp(2 * m.x88) + 1) + m.x66 == 1)
m.e86 = Constraint(expr= 2 / (exp(2 * m.x89) + 1) + m.x67 == 1)
m.e87 = Constraint(expr= 2 / (exp(2 * m.x90) + 1) + m.x68 == 1)
m.e88 = Constraint(expr= 2 / (exp(2 * m.x91) + 1) + m.x69 == 1)
m.e89 = Constraint(expr= 2 / (exp(2 * m.x92) + 1) + m.x70 == 1)
m.e90 = Constraint(expr= 2 / (exp(2 * m.x93) + 1) + m.x71 == 1)
m.e91 = Constraint(expr= 2 / (exp(2 * m.x94) + 1) + m.x72 == 1)
m.e92 = Constraint(expr= 2 / (exp(2 * m.x95) + 1) + m.x73 == 1)
m.e93 = Constraint(expr= 2 / (exp(2 * m.x96) + 1) + m.x74 == 1)
m.e94 = Constraint(expr= 0.94504 * m.x65 + 0.063174 * m.x66 + 1.23 * m.x67 +
    0.0045084 * m.x68 - 0.080538 * m.x69 + 0.0086604 * m.x70 - 0.027211 * m.x71
    + 0.013266 * m.x72 + 0.27219 * m.x73 + 1.7486 * m.x74 + m.x76
    == 0.411768749636318)
m.e95 = Constraint(expr= m.x75 - 143.0487213258034 * m.x76
    == 173.4064201136556)