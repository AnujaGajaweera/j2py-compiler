package core;

interface A { void a(); }
interface B { void b(); }

class Base {
    public void run() {
        System.out.println("Base");
    }
}

class Mid extends Base implements A {
    public void a() {}
}

class Child extends Mid implements B {
    public void b() {}

    @Override
    public void run() {
        super.run();
        System.out.println("Child");
    }
}