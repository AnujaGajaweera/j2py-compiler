package streams;

import java.util.*;
import java.util.stream.*;

public class CollectorChaos {

    public static void main(String[] args) {
        List<Integer> list = Arrays.asList(1,2,3,4,5,6,7,8);

        Map<String, List<Integer>> grouped =
            list.stream().collect(Collectors.groupingBy(
                x -> x % 2 == 0 ? "even" : "odd"
            ));

        System.out.println(grouped);
    }
}