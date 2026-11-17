import indicadores from "./indicadores.svg";
import sensorDeEstacionamiento from "./sensor-de-estacionamiento.svg";

export const Presentacin = () => {
  return (
    <main className="flex flex-col h-[272px] items-start relative overflow-hidden bg-[linear-gradient(125deg,rgba(255,141,40,1)_0%,rgba(255,162,79,1)_50%,rgba(255,255,255,1)_100%)] bg-colors-accents-orange">
      <header className="flex h-11 items-center justify-between px-5 py-0 relative self-stretch w-full">
        <time
          className="relative w-fit [font-family:'Inter-Bold',Helvetica] font-bold text-white text-xs tracking-[0] leading-[normal]"
          dateTime="09:41"
        >
          9:41
        </time>
        <img
          className="relative flex-[0_0_auto]"
          src={indicadores}
          alt="Indicadores de estado del dispositivo"
        />
      </header>
      <div
        className="absolute top-[55px] left-[206px] w-[180px] h-[180px] rounded-[28px] border-[24px] border-solid border-[#ffffff18] rotate-[22.00deg]"
        aria-hidden="true"
      />
      <div
        className="absolute top-[168px] -left-12 w-[490px] h-0.5 bg-[#ffffff1f]"
        aria-hidden="true"
      />
      <section className="flex items-center justify-between pt-4 pb-6 px-6 relative flex-1 self-stretch w-full grow">
        <div className="flex flex-col w-[206px] items-start gap-3 relative">
          <div className="inline-flex items-center gap-2 relative flex-[0_0_auto]">
            <div
              className="flex w-[42px] h-[42px] items-center justify-center relative bg-white rounded-[14px] overflow-hidden"
              aria-label="ParkIEST"
            >
              <span className="relative w-fit [font-family:'Inter-Black',Helvetica] font-black text-colors-accents-orange text-[21px] tracking-[0] leading-[normal] whitespace-nowrap">
                P
              </span>
            </div>
            <h1 className="relative w-fit [font-family:'Inter-ExtraBold',Helvetica] font-extrabold text-white text-xl tracking-[-0.08px] leading-[normal] whitespace-nowrap">
              ParkIEST
            </h1>
          </div>
          <p className="relative self-stretch [font-family:'Inter-Regular',Helvetica] font-normal text-white text-xl tracking-[0] leading-[23.6px]">
            Encuentra lugar antes de llegar.
          </p>
          <p className="relative self-stretch [font-family:'Inter-Regular',Helvetica] font-normal text-[#dce7ff] text-xs tracking-[0] leading-[17.4px]">
            Disponibilidad detectada en tiempo real.
          </p>
        </div>
        <img
          className="relative w-28 h-[142px]"
          src={sensorDeEstacionamiento}
          alt="Sensor de estacionamiento"
        />
      </section>
    </main>
  );
};
