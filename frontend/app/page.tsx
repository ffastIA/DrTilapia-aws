// CAMINHO: frontend/app/page.tsx
import Link from 'next/link';
import Image from 'next/image';
import { barlow, barlowCondensed } from '@/lib/fonts';
import styles from '@/styles/dr-tilapia.module.css';

const services = [
  {
    title: 'MELHOR APROVEITAMENTO DE CARCAÇA',
    body: 'Modelos preditivos utilizam biometria por visão computacional não invasiva e indicam quais ações devem ser tomadas para obter o melhor aproveitamento de carcaça.',
  },
  {
    title: 'Visão computacional',
    body: 'Câmeras subaquáticas e de superfície alimentam modelos de detecção que contam, medem e estimam o peso de cada lote sem estresse ao animal — biometria contínua, não amostral.',
  },
  {
    title: 'Consultoria aplicada',
    body: 'Nossa equipe de tecnologia e pesquisa está sempre atualizando sua consultoria virtual com o que há de mais atualizado para transformar sua produção em lucro.',
  },
];

function CornerMarks() {
  return (
    <>
      <i className={`${styles.corner} ${styles.cornerTl}`} />
      <i className={`${styles.corner} ${styles.cornerTr}`} />
      <i className={`${styles.corner} ${styles.cornerBl}`} />
      <i className={`${styles.corner} ${styles.cornerBr}`} />
    </>
  );
}

export default function HomePage() {
  return (
    <div className={`${barlow.variable} ${barlowCondensed.variable} ${styles.theme}`}>
      <nav className={styles.nav}>
        <span className={styles.navBrand}>
          <Image src="/LogoTAI.jpeg" alt="Dr. Tilap-IA" width={36} height={30} />
          Dr. Tilap-IA
        </span>
        <div className={styles.navLinks}>
          <a href="#servicos">Serviços</a>
          <a href="#sobre">Sobre</a>
          <Link href="/auth/login" className={styles.btn}>
            Entrar
          </Link>
          <Link href="/auth/signup" className={`${styles.btn} ${styles.btnPrimary}`}>
            Criar conta
          </Link>
        </div>
      </nav>

      <div className={styles.wrap}>
        <div className={styles.heroRow}>
          <div className={styles.heroPhoto}>
            <Image
              src="/ImagemSite01.png"
              alt="Foto de tanque de tilápia com câmera de monitoramento instalada"
              width={1024}
              height={1536}
            />
          </div>
          <section className={styles.hero}>
            <h1 className={styles.display}>
              <span>Inteligência Artificial Aplicada à Tilapiacultura</span>
            </h1>
            <p className={styles.sub}>
              Consultoria tecnológica que aplica inteligência artificial e visão computacional à
              piscicultura industrial: contagem e biometria por câmera, previsão de crescimento e
              ração ideal por lote, integrado ao seu manejo diário — dados de precisão onde antes
              havia estimativa.
            </p>
          </section>
        </div>

        <section className={styles.features} id="servicos">
          <div className={styles.cells}>
            {services.map((service) => (
              <div className={styles.cellFrame} key={service.title}>
                <CornerMarks />
                <h2>{service.title}</h2>
                <p>{service.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.split} id="sobre">
          <div>
            <span className={styles.kicker}>Sobre a consultoria</span>
            <hr className={styles.captionRule} />
            <h2 className={styles.splitTitle}>Pesquisa aplicada à produção</h2>
            <p className={styles.splitNote}>
              Somos uma consultoria de tecnologia formada por engenheiros de visão computacional e
              pesquisadores em aquicultura. Cada implantação nasce de um estudo do seu sistema de
              produção — não um pacote genérico — e é calibrada em campo antes de virar rotina.
            </p>
          </div>
          <figure className={styles.splitFigure}>
            <CornerMarks />
            <Image
              src="/ImagemSite01.png"
              alt="Produtor acompanhando o painel de produção da piscicultura"
              width={1024}
              height={1536}
            />
          </figure>
        </section>

        <footer className={styles.siteFooter}>
          DR. Tilap-IA — consultoria em IA e visão computacional para piscicultura.
        </footer>
      </div>
    </div>
  );
}
