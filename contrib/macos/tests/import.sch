v 20210407 2
C 1000 1000 1 0 0 diode-1.sym
{
T 1000 1600 5 10 1 1 0 0 1
refdes=D3
T 1000 1800 5 10 1 1 0 0 1
value=TVS, "test"\path
T 1000 2000 5 10 0 0 0 0 1
footprint=SOD123
T 1000 2200 5 10 0 0 0 0 1
manufacturer=Test, Inc.
}
C 3000 1100 1 0 0 resistor-1.sym
{
T 3000 1600 5 10 1 1 0 0 1
refdes=R1
T 3000 1800 5 10 1 1 0 0 1
value=10k
T 3000 2000 5 10 0 0 0 0 1
footprint=RESC1608N
}
N 500 1200 1000 1200 4
{
T 500 1400 5 10 1 1 0 0 1
netname=INPUT
}
N 1900 1200 3000 1200 4
{
T 1900 1400 5 10 1 1 0 0 1
netname=SIGNAL, (test)
}
N 3900 1200 4500 1200 4
{
T 4000 1400 5 10 1 1 0 0 1
netname=RETURN
}
