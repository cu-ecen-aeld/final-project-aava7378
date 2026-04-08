# STM32 Telemetry Firmware

This firmware runs on the STM32F103RB and performs:

- ADC acquisition (voltage + current)
- PWM generation (TIM3, 1 kHz)
- UART transmission using USART1 (115200 baud)

## Parse File Format

t_s,voltage_v,current_a,pwm_pct,pwm_freq_hz

## Pin Mapping

- PA0: Voltage ADC
- PA1: Current ADC
- PA6: PWM Output (TIM3_CH1)
- PA9: UART TX
- PA10: UART RX

## Clock

- SYSCLK: 72 MHz
