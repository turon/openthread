#ifndef _GPIO_H
#define _GPIO_H

#define LED_1 13
#define LED_2 14
#define LED_3 15
#define LED_4 16

static inline void gpio_init(int pin)
{
    (void)pin;
#ifdef NRF52840_XXAA
    NRF_GPIO->PIN_CNF[pin] = 1;
    NRF_GPIO->DIRSET = (1 << pin);
#endif
}

static inline void gpio_set(int pin)
{
    (void)pin;
#ifdef NRF52840_XXAA
    NRF_GPIO->OUTSET = (1 << pin);
#endif
}

static inline void gpio_clear(int pin)
{
    (void)pin;
#ifdef NRF52840_XXAA
    NRF_GPIO->OUTCLR = (1 << pin);
#endif
}

#endif // _GPIO_H
