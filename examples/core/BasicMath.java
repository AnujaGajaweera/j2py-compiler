package core;

public class BasicMath {

    public static int add(int a, int b) {
        return a + b;
    }

    public static int complex(int x) {
        return (((x + 2) * (x - 3)) / (x + 1)) + (x % 7);
    }

    public static void main(String[] args) {
        System.out.println(add(2, 3));
        System.out.println(complex(10));
    }
}