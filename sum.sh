awk -F, '{sum+=$2+$3} END {print sum}' $ASC
